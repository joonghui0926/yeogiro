from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

from yeogiro.calls import lines
from yeogiro.calls.session import CallDeps, CallSession, CallState
from yeogiro.ports import BookingRecord, Flags, Tester


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        async def method(*args: Any, **kwargs: Any) -> None:
            self.calls.append(name)

        return method


class Payments(Recorder):
    async def wait(self, payment_id: str, timeout: float) -> bool:
        self.calls.append("wait")
        return False


def make_session() -> tuple[CallSession, Recorder, Payments, list[str]]:
    rail = Recorder()
    payments = Payments()
    deps = CallDeps(
        voice=cast(Any, Recorder()),
        rail=cast(Any, rail),
        judge=cast(Any, Recorder()),
        payments=cast(Any, payments),
        messenger=cast(Any, Recorder()),
        store=cast(Any, Recorder()),
    )
    tester = Tester(id="t01", label="T01", alias="테스터", home_station="대전", senior=True)
    session = CallSession("call", "voice", tester, deps, Flags())
    said: list[str] = []

    async def say(text: str) -> None:
        said.append(text)

    session._say = say  # type: ignore[method-assign]
    return session, rail, payments, said


def hold_seat(session: CallSession) -> None:
    session._hold = cast(Any, SimpleNamespace(provider="mock"))
    session._booking = BookingRecord(
        id="b1",
        call_id="call",
        tester_id="t01",
        train_key="k",
        pnr="p",
        provider="mock",
        status="held",
        created_at=datetime.now(),
    )
    session._payment_id = "pay_1"


async def test_drop_before_any_proposal_asks_if_anything_else() -> None:
    session, rail, _, _ = make_session()
    result = await session._drop_trip({"heard": "안 갈래"})
    assert result["say"] == lines.TRIP_DROPPED
    assert session._outcome == "declined"
    assert session.state is CallState.LISTENING
    assert "cancel" not in rail.calls


async def test_drop_during_payment_releases_seat_and_withdraws_payment() -> None:
    session, rail, payments, _ = make_session()
    hold_seat(session)
    result = await session._drop_trip({"heard": "갑자기 가기 싫어졌어"})
    assert result["say"] == lines.TRIP_DROPPED
    assert "cancel" in rail.calls
    assert "expire" in payments.calls
    assert session._booking is not None and session._booking.status == "cancelled"
    assert session._payment_id is None
    assert session._outcome == "cancelled"
    assert session._current is None


async def test_payment_reminders_stop_once_trip_is_dropped() -> None:
    session, _, _, said = make_session()
    hold_seat(session)
    payment = cast(Any, SimpleNamespace(id="pay_1", amount=17600))
    await session._drop_trip({})
    await session._await_payment(cast(Any, None), payment)
    assert said == []


async def test_payment_reminders_stop_once_booking_is_cancelled() -> None:
    session, _, _, said = make_session()
    hold_seat(session)
    payment = cast(Any, SimpleNamespace(id="pay_1", amount=17600))
    await session._cancel_booking({})
    await session._await_payment(cast(Any, None), payment)
    assert said == []


async def test_goodbye_after_drop_is_thanks() -> None:
    session, _, _, said = make_session()

    async def end() -> None:
        return None

    session._end_after_speech = end  # type: ignore[method-assign]
    await session._drop_trip({})
    await session._say_goodbye_and_end()
    assert said == [lines.THANKS_GOODBYE]


async def test_new_search_after_drop_restores_trip_goodbye() -> None:
    session, _, _, said = make_session()

    async def end() -> None:
        return None

    session._end_after_speech = end  # type: ignore[method-assign]
    await session._drop_trip({})
    await session._find_trains({})  # no arrival: asks for it, but the caller is travelling again
    await session._say_goodbye_and_end()
    assert said == [lines.GOODBYE]
