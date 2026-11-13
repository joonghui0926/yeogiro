from __future__ import annotations

import asyncio
from datetime import date, time
from typing import Any

from google.cloud import firestore_v1 as firestore

from yeogiro.adapters.rail.codec import hold_from_dict, hold_to_dict, train_from_dict, train_to_dict
from yeogiro.domain.models import Hold, Train
from yeogiro.ports import HoldFailed, HoldRequest, RailUnavailable

JOBS = "railJobs"


class JobFailed(Exception):
    pass


class JobQueue:
    def __init__(self, db: firestore.AsyncClient) -> None:
        self._db = db

    async def run(
        self, kind: str, payload: dict[str, Any], handler: str, timeout: float, call_id: str
    ) -> dict[str, Any]:
        ref = self._db.collection(JOBS).document()
        await ref.set(self._job(kind, payload, handler, call_id))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        interval = 0.3 if handler == "worker" else 0.8
        while loop.time() < deadline:
            data = (await ref.get()).to_dict() or {}
            status = data.get("status")
            if status == "done":
                result: dict[str, Any] = data.get("result") or {}
                return result
            if status == "failed":
                raise JobFailed(str(data.get("error") or "failed"))
            await asyncio.sleep(interval)
        await ref.update({"status": "expired"})
        raise RailUnavailable(f"{kind} job timed out after {timeout:.0f}s")

    async def post(self, kind: str, payload: dict[str, Any], handler: str, call_id: str) -> None:
        await self._db.collection(JOBS).document().set(self._job(kind, payload, handler, call_id))

    @staticmethod
    def _job(kind: str, payload: dict[str, Any], handler: str, call_id: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "payload": payload,
            "handler": handler,
            "status": "pending",
            "callId": call_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }


class WorkerRail:
    """Korail through the worker on the team laptop, so the account never leaves that machine."""

    name = "korail"

    def __init__(self, queue: JobQueue, search_timeout: float, hold_timeout: float) -> None:
        self._queue = queue
        self._search_timeout = search_timeout
        self._hold_timeout = hold_timeout

    async def search(
        self, dep: str, arr: str, day: date, after: time | None = None, call_id: str = ""
    ) -> list[Train]:
        payload = {"dep": dep, "arr": arr, "day": day.isoformat(), "after": _clock(after)}
        try:
            result = await self._queue.run(
                "search", payload, "worker", self._search_timeout, call_id
            )
        except JobFailed as error:
            raise RailUnavailable(str(error)) from error
        return [train_from_dict(item) for item in result.get("trains", [])]

    async def hold(self, request: HoldRequest) -> Hold:
        payload = {
            "train": train_to_dict(request.train),
            "party": request.party,
            "senior": request.senior,
            "fareTotal": request.fare_total,
        }
        try:
            result = await self._queue.run(
                "hold", payload, "worker", self._hold_timeout, request.call_id
            )
        except JobFailed as error:
            raise HoldFailed(str(error)) from error
        return hold_from_dict(result["hold"])

    async def cancel(self, hold: Hold, call_id: str = "") -> None:
        await self._queue.post("cancel", {"hold": hold_to_dict(hold)}, "worker", call_id)


class AssistRail:
    """A teammate books in the 코레일+ app and types the reservation number into the console."""

    name = "assist"

    def __init__(self, queue: JobQueue, timeout: float) -> None:
        self._queue = queue
        self._timeout = timeout

    async def hold(self, request: HoldRequest) -> Hold:
        payload = {
            "train": train_to_dict(request.train),
            "party": request.party,
            "senior": request.senior,
            "fareTotal": request.fare_total,
        }
        try:
            result = await self._queue.run(
                "hold", payload, "operator", self._timeout, request.call_id
            )
        except JobFailed as error:
            raise HoldFailed(str(error)) from error
        return Hold(
            pnr=str(result["pnr"]),
            train=request.train,
            fare_total=int(result.get("fareTotal") or request.fare_total),
            seat=result.get("seat") or None,
            pay_by=None,
            provider=self.name,
        )

    async def cancel(self, hold: Hold, call_id: str = "") -> None:
        await self._queue.post("cancel", {"hold": hold_to_dict(hold)}, "operator", call_id)


def _clock(value: time | None) -> str | None:
    return value.strftime("%H%M%S") if value else None
