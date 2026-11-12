from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from google.cloud import firestore

from yeogiro.ports import BookingRecord, Flags, InboxMessage, RailMode, Tester

_FLAGS_TTL = 1.5
_TESTER_TTL = 30.0


class FirestoreStore:
    def __init__(self, db: firestore.AsyncClient) -> None:
        self._db = db
        self._flags: tuple[float, Flags] | None = None
        self._testers: dict[str, tuple[float, Tester]] = {}
        self._lock = asyncio.Lock()

    async def tester_by_token(self, token: str) -> Tester | None:
        cached = self._testers.get(token)
        if cached and time.monotonic() - cached[0] < _TESTER_TTL:
            return cached[1]
        query = self._db.collection("testers").where("token", "==", token).limit(1)
        async for snapshot in query.stream():
            tester = _tester(snapshot.id, snapshot.to_dict() or {})
            self._testers[token] = (time.monotonic(), tester)
            return tester
        return None

    async def set_tester_senior(self, tester_id: str, senior: bool) -> None:
        await self._db.collection("testers").document(tester_id).update({"senior": senior})
        self._testers.clear()

    async def flags(self) -> Flags:
        async with self._lock:
            if self._flags and time.monotonic() - self._flags[0] < _FLAGS_TTL:
                return self._flags[1]
            data = (await self._db.collection("config").document("runtime").get()).to_dict() or {}
            flags = Flags(
                booking_enabled=bool(data.get("bookingEnabled", True)),
                rail_mode=RailMode(data.get("railMode", RailMode.MOCK.value)),
                force_sold_out=bool(data.get("forceSoldOut", False)),
                phone_band=bool(data.get("phoneBand", False)),
            )
            self._flags = (time.monotonic(), flags)
            return flags

    async def create_call(self, call_id: str, data: Mapping[str, Any]) -> None:
        await self._db.collection("calls").document(call_id).set(dict(data))

    async def update_call(self, call_id: str, data: Mapping[str, Any]) -> None:
        await self._db.collection("calls").document(call_id).set(dict(data), merge=True)

    async def append_event(self, call_id: str, seq: int, data: Mapping[str, Any]) -> None:
        events = self._db.collection("calls").document(call_id).collection("events")
        await events.document(f"{seq:05d}").set(dict(data))

    async def bookings_for(self, tester_id: str) -> list[BookingRecord]:
        query = self._db.collection("bookings").where("testerId", "==", tester_id)
        records = []
        async for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            records.append(
                BookingRecord(
                    id=snapshot.id,
                    call_id=str(data.get("callId", "")),
                    tester_id=tester_id,
                    train_key=str(data.get("trainKey", "")),
                    pnr=str(data.get("pnr", "")),
                    provider=str(data.get("provider", "")),
                    status=str(data.get("status", "")),
                    created_at=_as_datetime(data.get("createdAt")),
                )
            )
        return records

    async def save_booking(self, booking: BookingRecord) -> None:
        await (
            self._db.collection("bookings")
            .document(booking.id)
            .set(
                {
                    "callId": booking.call_id,
                    "testerId": booking.tester_id,
                    "trainKey": booking.train_key,
                    "pnr": booking.pnr,
                    "provider": booking.provider,
                    "status": booking.status,
                    "createdAt": booking.created_at,
                    **booking.extra,
                },
                merge=True,
            )
        )

    async def save_payment(self, payment_id: str, data: Mapping[str, Any]) -> None:
        await self._db.collection("payments").document(payment_id).set(dict(data), merge=True)

    async def add_inbox_message(self, tester_id: str, message: InboxMessage) -> None:
        inbox = self._db.collection("inbox").document(tester_id).collection("messages")
        await inbox.document(message.id).set(
            {"sender": message.sender, "body": message.body, "sentAt": message.sent_at}
        )

    async def inbox(self, tester_id: str, limit: int = 50) -> list[InboxMessage]:
        query = (
            self._db.collection("inbox")
            .document(tester_id)
            .collection("messages")
            .order_by("sentAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        messages = []
        async for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            messages.append(
                InboxMessage(
                    id=snapshot.id,
                    sender=str(data.get("sender", "")),
                    body=str(data.get("body", "")),
                    sent_at=_as_datetime(data.get("sentAt")),
                )
            )
        return list(reversed(messages))


def _tester(tester_id: str, data: Mapping[str, Any]) -> Tester:
    senior = data.get("senior")
    return Tester(
        id=tester_id,
        label=str(data.get("label", tester_id)),
        alias=str(data.get("alias", "김여기")),
        home_station=data.get("homeStation") or None,
        senior=senior if isinstance(senior, bool) else None,
    )


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromtimestamp(0)
