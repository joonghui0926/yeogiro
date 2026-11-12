from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from yeogiro.calls.session import CallDeps, CallSession
from yeogiro.ports import BookingRecord, Flags, Tester


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        async def method(*args: Any, **kwargs: Any) -> None:
            self.calls.append(name)

        return method


def session_with_booking(status: str) -> tuple[CallSession, Recorder]:
    rail = Recorder()
    deps = CallDeps(
        voice=cast(Any, Recorder()),
        rail=cast(Any, rail),
        judge=cast(Any, Recorder()),
        payments=cast(Any, Recorder()),
        messenger=cast(Any, Recorder()),
        store=cast(Any, Recorder()),
    )
    tester = Tester(id="t01", label="T01", alias="테스터", home_station="대전", senior=True)
    session = CallSession("call", "voice", tester, deps, Flags())
    session._hold = cast(Any, SimpleNamespace(provider="mock"))
    session._booking = BookingRecord(
        id="b1",
        call_id="call",
        tester_id="t01",
        train_key="k",
        pnr="p",
        provider="mock",
        status=status,
        created_at=datetime.now(),
    )
    return session, rail


@pytest.mark.parametrize(("status", "kept"), [("paid", "paid"), ("held", "cancelled")])
async def test_hangup_releases_only_unpaid_holds(status: str, kept: str) -> None:
    session, rail = session_with_booking(status)
    await session.hangup("caller")
    assert session._booking is not None
    assert session._booking.status == kept
    assert ("cancel" in rail.calls) is (status != "paid")
