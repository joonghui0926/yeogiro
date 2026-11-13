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


async def test_caller_who_hangs_up_right_after_paying_still_gets_the_ticket() -> None:
    from yeogiro.adapters.messaging.inbox import InAppMessenger, mailbox_for
    from yeogiro.adapters.store.memory import MemoryStore
    from yeogiro.config import KST
    from yeogiro.domain.models import Hold, Train

    store = MemoryStore()
    deps = CallDeps(
        voice=cast(Any, Recorder()),
        rail=cast(Any, Recorder()),
        judge=cast(Any, Recorder()),
        payments=cast(Any, Recorder()),
        messenger=InAppMessenger(store),
        store=store,
    )
    tester = Tester(id="t01", label="T01", alias="테스터", home_station="대전", senior=True)
    session = CallSession("call", "voice", tester, deps, Flags(), "phone1aa")
    leaves = datetime(2026, 11, 14, 17, 57, tzinfo=KST)
    train = Train("4045", "KTX", "대전", "서울", leaves, leaves.replace(hour=19, minute=5), 21600, None)
    session._hold = Hold("35000068", train, 21600, "16호차 2D", None, "mock")
    session._booking = BookingRecord(
        id="b1", call_id="call", tester_id="t01", train_key="k", pnr="35000068",
        provider="mock", status="paid", created_at=datetime.now(),
    )
    await session.hangup("replaced")
    await session.hangup("caller")
    inbox = await store.inbox(mailbox_for("t01", "phone1aa"))
    assert [m.body.splitlines()[0] for m in inbox] == ["[여기로] 예약 확인"]
