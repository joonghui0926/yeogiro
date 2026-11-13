from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from yeogiro.adapters.messaging.inbox import InAppMessenger
from yeogiro.adapters.payment.mock_onetouch import MockOneTouch
from yeogiro.adapters.rail.codec import hold_from_dict, hold_to_dict, itinerary_to_dict
from yeogiro.adapters.rail.itineraries import TransferPolicy, TransferSearch
from yeogiro.adapters.rail.mock import MockRail
from yeogiro.adapters.rail.router import RailRouter
from yeogiro.adapters.rail.tago import TagoTimetable
from yeogiro.adapters.store.memory import MemoryStore
from yeogiro.calls.session import CallDeps, CallSession, CallState
from yeogiro.config import KST
from yeogiro.domain import fares, speech
from yeogiro.domain.consent import Verdict
from yeogiro.domain.models import Choice, Itinerary, Train, TravelWindow
from yeogiro.ports import Flags, HoldFailed, HoldRequest, RailMode, RailUnavailable
from yeogiro.ports import Tester as RailTester

DAY = date(2099, 11, 17)
EARLIEST = datetime(2099, 11, 16, tzinfo=KST)
WINDOW = TravelWindow(DAY, time(5), time(23, 59), time(10))


def train(
    no: str, dep: str, arr: str, hour: int, minute: int = 0, ride: int = 60, day: date = DAY
) -> Train:
    start = datetime.combine(day, time(hour, minute), KST)
    return Train(no, "KTX", dep, arr, start, start + timedelta(minutes=ride), 10000, None)


class Timetable(TagoTimetable):
    def __init__(self, trains: list[Train], fail: bool = False) -> None:
        self.trains = trains
        self.fail = fail
        self.queries: list[tuple[str, str, date]] = []

    async def search(self, dep: str, arr: str, day: date) -> list[Train]:
        self.queries.append((dep, arr, day))
        if self.fail:
            raise RailUnavailable("offline")
        return [t for t in self.trains if (t.dep, t.arr, t.departs_at.date()) == (dep, arr, day)]

    async def station_names(self) -> list[str]:
        return sorted({s for t in self.trains for s in (t.dep, t.arr)})


def engine(timetable: Timetable, **options: Any) -> TransferSearch:
    return TransferSearch(timetable.search, timetable.station_names, TransferPolicy(**options))


def router(timetable: Timetable, mock: MockRail | None = None) -> RailRouter:
    return RailRouter(timetable, mock or MockRail(), None, None)


def connection() -> list[Train]:
    return [
        train("101", "대전", "이름없는중간역", 9),
        train("201", "이름없는중간역", "강릉", 10, 30),
    ]


async def test_direct_preserves_recommendation_and_skips_transfer_queries() -> None:
    direct = train("1", "대전", "강릉", 10)
    timetable = Timetable([direct, *connection()])
    result = await router(timetable).search_routes(
        "대전", "강릉", WINDOW, EARLIEST, RailMode.MOCK, "c"
    )
    assert result.routes == (Itinerary((direct,)),)
    assert timetable.queries == [("대전", "강릉", DAY)]


async def test_transfer_uses_directory_station_not_hardcoded_hubs() -> None:
    result = await engine(Timetable(connection())).search("대전", "강릉", WINDOW, EARLIEST)
    assert result.complete and not result.direct_found
    assert result.routes == (Itinerary(tuple(connection())),)
    data = itinerary_to_dict(result.routes[0])
    assert data["waitMinutes"] == 30 and data["durationMinutes"] == 150
    assert data["fare"] == 20000 and data["seatAvailability"] == "unknown"


@pytest.mark.parametrize(
    "second",
    [
        train("2", "이름없는중간역", "강릉", 9, 30),
        train("2", "이름없는중간역", "강릉", 10, 19),
        train("2", "이름없는중간역", "강릉", 13, 1),
    ],
)
async def test_rejects_time_order_short_or_excessive_wait(second: Train) -> None:
    result = await engine(Timetable([connection()[0], second])).search(
        "대전", "강릉", WINDOW, EARLIEST
    )
    assert result.routes == () and result.complete


@pytest.mark.parametrize("minute", [20, 180])
async def test_accepts_configured_wait_boundaries(minute: int) -> None:
    first = connection()[0]
    start = first.arrives_at + timedelta(minutes=minute)
    second = replace(connection()[1], departs_at=start, arrives_at=start + timedelta(hours=1))
    result = await engine(Timetable([first, second])).search("대전", "강릉", WINDOW, EARLIEST)
    assert len(result.routes) == 1


@pytest.mark.parametrize("first_hour,ride,second_hour", [(23, 30, 0), (23, 90, 1), (22, 60, 23)])
async def test_midnight_arrival_and_next_day_boarding(
    first_hour: int, ride: int, second_hour: int
) -> None:
    first = train("1", "대전", "중간역", first_hour, ride=ride)
    second_day = DAY + timedelta(days=1) if second_hour < first_hour else DAY
    second = train("2", "중간역", "강릉", second_hour, 30, ride=90, day=second_day)
    timetable = Timetable([first, second])
    result = await engine(timetable).search("대전", "강릉", WINDOW, EARLIEST)
    assert result.routes == (Itinerary((first, second)),)
    assert result.routes[0].legs[-1].arrives_at.date() == DAY + timedelta(days=1)
    assert ("중간역", "강릉", second_day) in timetable.queries


async def test_no_routes_is_distinct_from_api_failure() -> None:
    empty = await engine(Timetable([])).search("대전", "강릉", WINDOW, EARLIEST)
    failed = await engine(Timetable([], fail=True)).search("대전", "강릉", WINDOW, EARLIEST)
    assert empty.complete and not empty.api_failed and not empty.routes
    assert not failed.complete and failed.api_failed and not failed.routes
    with pytest.raises(RailUnavailable):
        await router(Timetable([], fail=True)).search("대전", "강릉", DAY, None, RailMode.MOCK, "c")


async def test_duplicate_routes_and_same_train_are_removed() -> None:
    trains = connection()
    result = await engine(Timetable(trains * 3)).search("대전", "강릉", WINDOW, EARLIEST)
    assert len(result.routes) == 1
    trains[1] = replace(trains[1], train_no=trains[0].train_no)
    assert not (await engine(Timetable(trains)).search("대전", "강릉", WINDOW, EARLIEST)).routes


async def test_routes_sorted_by_duration_and_arrival() -> None:
    trains = [*connection(), train("3", "대전", "다른역", 8), train("4", "다른역", "강릉", 9, 20)]
    result = await engine(Timetable(trains)).search("대전", "강릉", WINDOW, EARLIEST)
    assert [r.wait_minutes for r in result.routes] == [20, 30]


async def test_query_budget_and_deadline_report_incomplete() -> None:
    timetable = Timetable(connection())
    limited = await engine(timetable, max_queries=1).search("대전", "강릉", WINDOW, EARLIEST)
    assert not limited.complete and len(timetable.queries) == 1

    async def slow(*args: Any) -> list[Train]:
        await asyncio.sleep(1)
        return []

    service = TransferSearch(slow, timetable.station_names, TransferPolicy(timeout_seconds=0.01))
    result = await service.search("대전", "강릉", WINDOW, EARLIEST)
    assert not result.complete and not result.api_failed


async def test_direct_and_transfer_alternatives_and_unsuitable_direct() -> None:
    direct = train("9", "대전", "강릉", 18)
    timetable = Timetable([direct, *connection()])
    rail = router(timetable)
    result = await rail.search_routes("대전", "강릉", WINDOW, EARLIEST, RailMode.MOCK, "c", True)
    assert [len(r.legs) for r in result.routes] == [1, 2]
    morning = replace(WINDOW, end=time(12))
    result = await rail.search_routes("대전", "강릉", morning, EARLIEST, RailMode.MOCK, "c")
    assert any(len(r.legs) == 2 for r in result.routes)


def call_session(timetable: Timetable) -> tuple[CallSession, MemoryStore]:
    store = MemoryStore()
    session = CallSession(
        "c",
        "v",
        RailTester("demo", "테스트", "테스트", "대전", False),
        CallDeps(
            AsyncMock(),
            router(timetable),
            AsyncMock(),
            MockOneTouch(store),
            InAppMessenger(store),
            store,
        ),
        Flags(),
    )
    return session, store


def args() -> dict[str, Any]:
    return {
        "departure": "대전",
        "arrival": "강릉",
        "relative_day": "date",
        "month": DAY.month,
        "day_of_month": DAY.day,
    }


async def test_transfer_reaches_voice_consent_booking_payment_and_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Resolve the calendar against the real test clock without relying on a live API/model.
    day = datetime.now(KST).date() + timedelta(days=1)
    trains = [
        replace(
            t,
            departs_at=datetime.combine(day, t.departs_at.time(), KST),
            arrives_at=datetime.combine(day, t.arrives_at.time(), KST),
        )
        for t in connection()
    ]
    session, store = call_session(Timetable(trains))
    session._deps.judge.judge.return_value = (Verdict.YES, "전체 여정 동의")
    monkeypatch.setattr("yeogiro.calls.session.SMS_DELAY_SECONDS", 0)
    monkeypatch.setattr(session, "_say", AsyncMock())
    result = await session._find_trains({**args(), "relative_day": "tomorrow"})
    assert result["status"] == "transfer_found"
    assert result["itinerary"]["legs"][1]["arr"] == "강릉"
    assert "직통 열차는 조회되지 않았지만" in result["say"]
    assert "101번" in result["say"] and "201번" in result["say_short"]
    assert "모의 예약" in result["say"] and "미확인" not in result["facts"]["요금"]
    assert result["facts"]["구간"] == "대전에서 강릉"
    session._proposal_completed = True
    session._replies = ["두 구간 모두 예약해 주세요"]
    booked = await session._request_booking({"option_id": result["option_id"]})
    assert booked["ok"] and session.state is CallState.PAYMENT_PENDING
    hold = session._hold
    assert hold is not None and len(hold.leg_holds) == 2
    assert hold.provider == "mock" and hold.fare_total == 20000
    assert hold_from_dict(hold_to_dict(hold)) == hold
    assert len(store.bookings["bk_c"].extra["legHolds"]) == 2
    assert session._payment_id is not None
    assert store.payments[session._payment_id]["amount"] == 20000
    assert "강릉" in store.payments[session._payment_id]["item"]
    await session.approve_payment(session._payment_id)
    await asyncio.gather(*session._tasks)
    assert store.bookings["bk_c"].status == "paid"
    message = store.messages["demo"][0].body
    assert all(h.pnr in message for h in hold.leg_holds)
    assert "별도 예약" in message and "실제 좌석 확보" in message
    await session.hangup("caller")


@pytest.mark.parametrize("fail,status", [(False, "no_route"), (True, "api_error")])
async def test_voice_distinguishes_empty_from_error_and_invalidates_old_proposal(
    fail: bool, status: str
) -> None:
    session, _ = call_session(Timetable([], fail=fail))
    result = await session._find_trains(args())
    assert result["status"] == status and "기차표가 없" not in result["say"]
    assert session._current is None and session.state is CallState.LISTENING
    await session.hangup("caller")


async def test_partial_hold_failure_rolls_back_first_leg() -> None:
    mock = MockRail()
    first = await mock.hold(hold_request(connection()[0]))
    mock.hold = AsyncMock(side_effect=[first, HoldFailed("second failed")])
    mock.cancel = AsyncMock()
    rail = router(Timetable(connection()), mock)
    with pytest.raises(HoldFailed):
        await rail.hold_route(
            hold_request(connection()[0]), Itinerary(tuple(connection())), RailMode.AUTO
        )
    mock.cancel.assert_awaited_once_with(first)


def hold_request(t: Train) -> HoldRequest:
    return HoldRequest("c", "demo", t, 1, False, 20000)


@pytest.mark.parametrize("verdict,heard", [(Verdict.UNCLEAR, True), (Verdict.YES, False)])
async def test_transfer_gate_requires_consent_and_complete_playback(
    verdict: Verdict, heard: bool
) -> None:
    session, store = call_session(Timetable(connection()))
    proposal = session._propose(Choice(connection()[0], None, Itinerary(tuple(connection()))), 1)
    session._deps.judge.judge.return_value = (verdict, "fixture")
    session._proposal_completed = heard
    session._replies = ["음"]
    result = await session._request_booking({"option_id": proposal["option_id"]})
    assert not result["ok"] and not store.bookings and not store.payments
    assert "201번" in result["say"]
    await session.hangup("caller")


async def test_new_failed_search_invalidates_a_previously_accepted_option() -> None:
    session, store = call_session(Timetable([]))
    old = session._propose(Choice(connection()[0], None, Itinerary(tuple(connection()))), 1)
    session._proposal_completed = True
    await session._find_trains(args())
    session._deps.judge.judge.return_value = (Verdict.YES, "old yes")
    result = await session._request_booking({"option_id": old["option_id"]})
    assert not result["ok"] and not store.bookings and session._current is None
    await session.hangup("caller")


async def test_unknown_segment_fare_blocks_payment_without_announcing_zero_total() -> None:
    trains = [connection()[0], replace(connection()[1], fare=0)]
    session, store = call_session(Timetable(trains))
    proposal = session._propose(Choice(trains[0], None, Itinerary(tuple(trains))), 1)
    assert proposal["itinerary"]["fare"] is None and proposal["train"]["fareTotal"] is None
    assert "운임 미확인" in proposal["facts"]["요금"]
    assert session._current is not None
    result = await session._secure(session._current)
    assert not result.ok and not store.bookings and not store.payments
    await session.hangup("caller")


async def test_transfer_cancel_releases_both_separate_holds() -> None:
    mock = MockRail()
    rail = router(Timetable(connection()), mock)
    mock.cancel = AsyncMock()
    hold = await rail.hold_route(
        hold_request(connection()[0]), Itinerary(tuple(connection())), RailMode.ASSIST
    )
    assert hold.provider == "mock"
    await rail.cancel(hold, "c")
    assert mock.cancel.await_count == 2
    assert [c.args[0] for c in mock.cancel.await_args_list] == list(hold.leg_holds)


async def test_next_day_speech_and_senior_fares_follow_each_leg_date() -> None:
    friday = date(2099, 11, 20)
    assert friday.weekday() == 4
    first = train("1", "대전", "중간역", 23, ride=30, day=friday)
    second = train("2", "중간역", "강릉", 0, 30, day=friday + timedelta(days=1))
    session, _ = call_session(Timetable([first, second]))
    session._senior = True
    result = session._propose(Choice(first, None, Itinerary((first, second))), 2)
    assert "11월 21일" in result["say"]
    assert result["train"]["fareTotal"] == 37000  # Friday: 7,000+10,000; Saturday: 20,000.
    assert fares.fare_total(first, 2, True) == 17000
    assert "21일" in result["facts"]["도착"]
    assert speech.route_description(Itinerary((first, second))) in result["say_short"]
    await session.hangup("caller")


async def test_partial_api_error_keeps_valid_paths_but_marks_search_incomplete() -> None:
    class Partial(Timetable):
        async def station_names(self) -> list[str]:
            return ["오류역", "이름없는중간역"]

        async def search(self, dep: str, arr: str, day: date) -> list[Train]:
            if arr == "오류역":
                raise RailUnavailable("one failed candidate")
            return await super().search(dep, arr, day)

    result = await engine(Partial(connection())).search("대전", "강릉", WINDOW, EARLIEST)
    assert len(result.routes) == 1 and result.api_failed and not result.complete


async def test_tago_outage_stops_after_three_consecutive_failures() -> None:
    class Offline(Timetable):
        async def station_names(self) -> list[str]:
            return [f"station{i}" for i in range(100)]

    timetable = Offline([], fail=True)
    result = await engine(timetable).search("대전", "강릉", WINDOW, EARLIEST)
    assert result.api_failed and not result.complete and len(timetable.queries) <= 3


async def test_explicit_transfer_selection_and_later_journey_keep_final_destination() -> None:
    day = datetime.now(KST).date() + timedelta(days=1)
    trains = [
        train("101", "대전", "중간역", 9, day=day),
        train("201", "중간역", "강릉", 10, 30, day=day),
        train("102", "대전", "중간역", 10, day=day),
        train("202", "중간역", "강릉", 11, 30, day=day),
        *(train(str(n), "대전", "강릉", 10, day=day) for n in range(10, 30)),
    ]
    session, _ = call_session(Timetable(trains))
    direct = await session._find_trains(
        {"arrival": "강릉", "relative_day": "tomorrow", "include_transfers": True}
    )
    assert direct["status"] == "direct_found"
    assert any(r["kind"] == "transfer" for r in direct["alternatives"])
    transfer = await session._find_trains(
        {"arrival": "강릉", "relative_day": "tomorrow", "prefer_transfer": True}
    )
    assert transfer["status"] == "transfer_found" and transfer["train"]["trainNo"] == "101"
    later = await session._find_trains({"shift": "later"})
    assert later["status"] == "transfer_found" and later["train"]["trainNo"] == "102"
    assert later["itinerary"]["legs"][-1]["arr"] == "강릉"
    await session.hangup("caller")


def test_long_journey_duration_does_not_wrap_at_twelve_hours() -> None:
    assert speech.read_duration(13 * 60) == "십삼 시간"
    assert speech.read_duration(24 * 60) == "이십사 시간"


async def test_tago_pagination_cache_unknown_seats_and_safe_errors() -> None:
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        page = int(request.url.params["pageNo"])
        item = {
            "trainno": str(page),
            "traingradename": "KTX",
            "adultcharge": 10000,
            "depplandtime": "20991117090000",
            "arrplandtime": "20991117100000",
        }
        return httpx.Response(
            200,
            json={
                "response": {
                    "header": {"resultCode": "00"},
                    "body": {"items": {"item": item}, "totalCount": 2},
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        tago = TagoTimetable("secret-key", http)
        tago._stations = {"대전": "a", "강릉": "b"}
        trains = await tago.search("대전", "강릉", DAY)
        assert len(trains) == 2 and all(t.seats_available is None for t in trains)
        assert await tago.search("대전", "강릉", DAY) == trains
        assert len(calls) == 2
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503))
    ) as http:
        tago = TagoTimetable("secret-key", http)
        tago._stations = {"대전": "a", "강릉": "b"}
        with pytest.raises(RailUnavailable) as error:
            await tago.search("대전", "강릉", DAY)
        assert "secret-key" not in str(error.value)
