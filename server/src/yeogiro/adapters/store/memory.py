from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from yeogiro.ports import BookingRecord, Flags, InboxMessage, Tester

DEMO_TESTER = Tester(id="demo", label="데모", alias="김여기", home_station="대전", senior=None)


class MemoryStore:
    """Local development and tests. Nothing survives a restart."""

    def __init__(self, testers: Mapping[str, Tester] | None = None, flags: Flags | None = None):
        self.testers: dict[str, Tester] = dict(testers or {"demo": DEMO_TESTER})
        self.current_flags = flags or Flags()
        self.calls: dict[str, dict[str, Any]] = {}
        self.events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.bookings: dict[str, BookingRecord] = {}
        self.payments: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, list[InboxMessage]] = defaultdict(list)

    async def tester_by_token(self, token: str) -> Tester | None:
        return self.testers.get(token)

    async def set_tester_senior(self, tester_id: str, senior: bool) -> None:
        for token, tester in self.testers.items():
            if tester.id == tester_id:
                self.testers[token] = replace(tester, senior=senior)

    async def flags(self) -> Flags:
        return self.current_flags

    async def create_call(self, call_id: str, data: Mapping[str, Any]) -> None:
        self.calls[call_id] = dict(data)

    async def update_call(self, call_id: str, data: Mapping[str, Any]) -> None:
        self.calls.setdefault(call_id, {}).update(data)

    async def append_event(self, call_id: str, seq: int, data: Mapping[str, Any]) -> None:
        self.events[call_id].append({"seq": seq, **data})

    async def bookings_for(self, tester_id: str) -> list[BookingRecord]:
        return [b for b in self.bookings.values() if b.tester_id == tester_id]

    async def save_booking(self, booking: BookingRecord) -> None:
        self.bookings[booking.id] = booking

    async def save_payment(self, payment_id: str, data: Mapping[str, Any]) -> None:
        self.payments.setdefault(payment_id, {}).update(data)

    async def add_inbox_message(self, tester_id: str, message: InboxMessage) -> None:
        self.messages[tester_id].append(message)

    async def inbox(self, tester_id: str, limit: int = 50) -> list[InboxMessage]:
        return self.messages[tester_id][-limit:]
