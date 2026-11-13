from datetime import datetime, time, timedelta
from typing import Any, cast

from yeogiro.adapters.messaging.inbox import InAppMessenger, mailbox_for
from yeogiro.adapters.payment.mock_onetouch import MockOneTouch
from yeogiro.adapters.rail.mock import MockRail
from yeogiro.adapters.rail.router import RailRouter
from yeogiro.adapters.store.memory import MemoryStore
from yeogiro.calls.session import CallDeps, CallSession, CallState
from yeogiro.config import KST
from yeogiro.domain.models import Choice, Hold
from yeogiro.domain.when import PartOfDay, resolve_window
from yeogiro.ports import Flags
from yeogiro.ports import Tester as Caller

TESTER = Caller(id="t01", label="T01", alias="김순자", home_station="대전", senior=False)


class Recorder:
    def __getattr__(self, name: str) -> Any:
        async def method(*args: Any, **kwargs: Any) -> None:
            return None

        return method


def make_session() -> tuple[CallSession, MemoryStore, MockRail]:
    store = MemoryStore()
    mock = MockRail()
    deps = CallDeps(
        voice=cast(Any, Recorder()),
        rail=RailRouter(mock, mock, None, None),
        judge=cast(Any, Recorder()),
        payments=MockOneTouch(store),
        messenger=InAppMessenger(store),
        store=store,
    )
    return CallSession("call", "voice", TESTER, deps, Flags(), "phone1aa"), store, mock


async def offer(session: CallSession, mock: MockRail, index: int = 0) -> None:
    day = datetime.now(KST).date() + timedelta(days=1)
    trains = await mock.search("대전", "서울", day)
    session._propose(Choice(trains[index], None), 1)


async def test_second_paid_booking_gets_its_own_record_and_ticket() -> None:
    session, store, mock = make_session()
    for index in (0, 3):
        await offer(session, mock, index)
        assert session._current is not None
        await session._secure(session._current)
        assert session._payment_id is not None
        assert await session.approve_payment(session._payment_id)
        assert session._hold is not None
        await session._send_ticket(session._hold)
    assert sorted(store.bookings) == ["bk_call", "bk_call_2"]
    assert all(b.status == "paid" for b in store.bookings.values())
    tickets = await store.inbox(mailbox_for("t01", "phone1aa"))
    assert len(tickets) == 2
    await session.hangup("caller")


async def test_booking_request_while_waiting_for_payment_is_refused() -> None:
    session, store, mock = make_session()
    await offer(session, mock)
    assert session._current is not None
    await session._secure(session._current)
    assert session.state is CallState.PAYMENT_PENDING
    result = await session._request_booking({"option_id": session._current.option_id})
    assert result is not None and result["reason"] == "busy"
    assert len(store.bookings) == 1 and len(store.payments) == 1
    await session.hangup("caller")


async def test_hangup_right_after_approval_keeps_the_paid_seat_and_sends_the_ticket() -> None:
    session, store, mock = make_session()
    await offer(session, mock)
    assert session._current is not None
    await session._secure(session._current)
    assert session._payment_id is not None
    assert await session.approve_payment(session._payment_id)
    await session.hangup("caller")
    assert store.bookings["bk_call"].status == "paid"
    assert store.calls["call"]["outcome"] == "booked"
    assert len(await store.inbox(mailbox_for("t01", "phone1aa"))) == 1


async def test_hangup_while_the_seat_is_being_secured_releases_it() -> None:
    session, store, mock = make_session()
    await offer(session, mock)
    real_hold = mock.hold

    async def slow_hold(request: Any) -> Hold:
        held = await real_hold(request)
        session._closed.set()
        return held

    mock.hold = slow_hold  # type: ignore[method-assign]
    assert session._current is not None
    secured = await session._secure(session._current)
    assert not secured.ok and not store.payments
    assert store.bookings["bk_call"].status == "cancelled"


async def test_reconnecting_phone_gets_the_pending_payment_again() -> None:
    session, _, mock = make_session()
    await offer(session, mock)
    assert session._current is not None
    await session._secure(session._current)
    queue = session.subscribe()
    assert queue.get_nowait()["type"] == "payment.requested"
    session.unsubscribe(queue)
    await session.hangup("caller")


def test_arrival_said_in_the_morning_means_the_afternoon() -> None:
    now = datetime(2026, 11, 13, 9, 0, tzinfo=KST)
    day = now.date() + timedelta(days=1)
    window = resolve_window(day, PartOfDay.MORNING, "08:00", now, "02:00")
    assert window.anchor == "arrives" and window.asked == time(14, 0)
