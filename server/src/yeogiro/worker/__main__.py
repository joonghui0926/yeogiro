from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import date, datetime, time
from typing import Any

from google.cloud import firestore_v1 as firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from yeogiro.adapters.rail.codec import (
    hold_from_dict,
    hold_to_dict,
    train_from_dict,
    train_to_dict,
)
from yeogiro.adapters.rail.jobs import JOBS
from yeogiro.adapters.rail.korail import KorailClient
from yeogiro.config import KST, load_settings

log = logging.getLogger("yeogiro.worker")


class RailWorker:
    def __init__(self, project: str, client: KorailClient) -> None:
        self._db = firestore.AsyncClient(project=project)
        self._listener_db = firestore.Client(project=project)
        self._client = client
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def serve(self) -> None:
        await asyncio.to_thread(self._client.login)
        log.info("korail login ok, waiting for jobs")
        loop = asyncio.get_running_loop()

        def on_snapshot(snapshots: list[Any], changes: Any, read_time: Any) -> None:
            for snapshot in snapshots:
                loop.call_soon_threadsafe(self._queue.put_nowait, snapshot.id)

        query = (
            self._listener_db.collection(JOBS)
            .where(filter=FieldFilter("handler", "==", "worker"))
            .where(filter=FieldFilter("status", "==", "pending"))
        )
        watch = query.on_snapshot(on_snapshot)
        try:
            while True:
                job_id = await self._queue.get()
                async with self._lock:
                    await self._handle(job_id)
        finally:
            watch.unsubscribe()  # type: ignore[no-untyped-call]

    async def _handle(self, job_id: str) -> None:
        ref = self._db.collection(JOBS).document(job_id)
        job = await self._claim(ref)
        if job is None:
            return
        kind, payload = job["kind"], job.get("payload", {})
        log.info("job %s %s", job_id, kind)
        try:
            result = await self._run(kind, payload)
        except Exception as error:
            log.warning("job %s failed: %s", job_id, error)
            await ref.update(
                {"status": "failed", "error": str(error), "doneAt": firestore.SERVER_TIMESTAMP}
            )
            return
        await ref.update({"status": "done", "result": result, "doneAt": firestore.SERVER_TIMESTAMP})

    async def _claim(self, ref: firestore.AsyncDocumentReference) -> dict[str, Any] | None:
        transaction = self._db.transaction()

        @firestore.async_transactional
        async def claim(tx: firestore.AsyncTransaction) -> dict[str, Any] | None:
            snapshot = await ref.get(transaction=tx)
            data = snapshot.to_dict() or {}
            if data.get("status") != "pending":
                return None
            tx.update(ref, {"status": "claimed", "claimedAt": firestore.SERVER_TIMESTAMP})
            return data

        job: dict[str, Any] | None = await claim(transaction)
        return job

    async def _run(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if kind == "search":
            after = payload.get("after")
            trains = await asyncio.to_thread(
                self._client.search,
                payload["dep"],
                payload["arr"],
                date.fromisoformat(payload["day"]),
                datetime.strptime(after, "%H%M%S").time() if after else None,
            )
            return {"trains": [train_to_dict(train) for train in trains]}
        if kind == "hold":
            hold = await asyncio.to_thread(
                self._client.hold,
                train_from_dict(payload["train"]),
                int(payload.get("party", 1)),
                bool(payload.get("senior", False)),
            )
            data = hold_to_dict(hold)
            if not data["fareTotal"]:
                data["fareTotal"] = int(payload.get("fareTotal", 0))
            return {"hold": data}
        if kind == "cancel":
            hold = hold_from_dict(payload["hold"])
            cancelled = await asyncio.to_thread(self._client.cancel, hold.pnr)
            return {"cancelled": cancelled}
        raise ValueError(f"unknown job kind {kind}")


def preflight(client: KorailClient) -> None:
    client.login()
    print("login ok")
    now = datetime.now(KST)
    trains = client.search("대전", "서울", now.date(), time(now.hour, 0))
    print(f"대전→서울 {now:%m/%d} {len(trains)} trains")
    for train in trains[:5]:
        seats = "좌석 있음" if train.seats_available else "매진"
        print(
            f"  {train.grade} {train.train_no} {train.departs_at:%H:%M}→{train.arrives_at:%H:%M} {seats}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m yeogiro.worker")
    parser.add_argument("--check", action="store_true", help="log in and search once, then exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs each request URL at INFO, and public-data URLs carry the service key.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = load_settings()
    member_id, password = os.environ.get("KORAIL_ID"), os.environ.get("KORAIL_PW")
    if not member_id or not password:
        raise SystemExit("KORAIL_ID and KORAIL_PW must be set in .env")
    client = KorailClient(member_id, password)
    if args.check:
        preflight(client)
        return
    asyncio.run(RailWorker(settings.firebase_project, client).serve())


if __name__ == "__main__":
    main()
