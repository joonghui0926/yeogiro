from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from types import TracebackType
from typing import Any, Protocol, Self

from yeogiro.domain.consent import Verdict
from yeogiro.domain.models import Hold, Train


class RailMode(StrEnum):
    AUTO = "auto"
    ASSIST = "assist"
    MOCK = "mock"


@dataclass(frozen=True, slots=True)
class Tester:
    id: str
    label: str
    alias: str
    home_station: str | None
    senior: bool | None


@dataclass(frozen=True, slots=True)
class Flags:
    booking_enabled: bool = True
    rail_mode: RailMode = RailMode.MOCK
    force_sold_out: bool = False
    phone_band: bool = False


@dataclass(frozen=True, slots=True)
class HoldRequest:
    call_id: str
    tester_id: str
    train: Train
    party: int
    senior: bool
    fare_total: int


@dataclass(frozen=True, slots=True)
class InboxMessage:
    id: str
    sender: str
    body: str
    sent_at: datetime


@dataclass(slots=True)
class BookingRecord:
    id: str
    call_id: str
    tester_id: str
    train_key: str
    pnr: str
    provider: str
    status: str
    created_at: datetime
    extra: dict[str, Any] = field(default_factory=dict)


class RailUnavailable(Exception):
    pass


class HoldFailed(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class VoiceChannel(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def send(self, event: dict[str, Any]) -> None: ...

    def events(self) -> AsyncIterator[dict[str, Any]]: ...

    async def close(self) -> None: ...


class VoiceCalls(Protocol):
    def attach(self, call_id: str) -> VoiceChannel: ...

    async def hangup(self, call_id: str) -> None: ...


class RailProvider(Protocol):
    name: str

    async def search(self, dep: str, arr: str, day: date) -> list[Train]: ...

    async def hold(self, request: HoldRequest) -> Hold: ...

    async def cancel(self, hold: Hold) -> None: ...


class ConsentJudge(Protocol):
    async def judge(self, proposal: str, replies: list[str]) -> tuple[Verdict, str]: ...


class Store(Protocol):
    async def tester_by_token(self, token: str) -> Tester | None: ...

    async def set_tester_senior(self, tester_id: str, senior: bool) -> None: ...

    async def flags(self) -> Flags: ...

    async def create_call(self, call_id: str, data: Mapping[str, Any]) -> None: ...

    async def update_call(self, call_id: str, data: Mapping[str, Any]) -> None: ...

    async def append_event(self, call_id: str, seq: int, data: Mapping[str, Any]) -> None: ...

    async def bookings_for(self, tester_id: str) -> list[BookingRecord]: ...

    async def save_booking(self, booking: BookingRecord) -> None: ...

    async def save_payment(self, payment_id: str, data: Mapping[str, Any]) -> None: ...

    async def add_inbox_message(self, tester_id: str, message: InboxMessage) -> None: ...

    async def inbox(self, tester_id: str, limit: int = 50) -> list[InboxMessage]: ...
