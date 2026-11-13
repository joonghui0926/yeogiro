from datetime import date, datetime, timedelta
from itertools import pairwise

from yeogiro.adapters.rail.korail_runs import connections, sample_day
from yeogiro.config import KST
from yeogiro.domain.routing import Connection, Timetable

DAY = date(2026, 11, 14)


def at(hhmm: str) -> datetime:
    return datetime.combine(DAY, datetime.strptime(hhmm, "%H:%M").time(), KST)


def run(train: str, *stops: tuple[str, str]) -> list[Connection]:
    return [
        Connection(train, a, b, at(t1), at(t2))
        for (a, t1), (b, t2) in pairwise(stops)
    ]


def test_finds_transfer_at_the_hub_when_there_is_no_direct_train() -> None:
    table = Timetable(
        run("6", ("대전", "07:17"), ("서울", "08:32"))
        + run("807", ("서울", "08:57"), ("강릉", "11:09"))
        + run("369", ("대전", "07:32"), ("경주", "08:37"))
        + run("751", ("경주", "08:57"), ("강릉", "11:45"))
    )
    best = table.earliest("대전", "강릉", at("06:00"), max_legs=2)
    assert [(leg.train_no, leg.dep, leg.arr) for leg in best[-1].legs] == [("6", "대전", "서울"), ("807", "서울", "강릉")]


def test_transfer_needs_the_minimum_connection_time() -> None:
    table = Timetable(
        run("1", ("대전", "07:00"), ("서울", "08:00"))
        + run("2", ("서울", "08:10"), ("강릉", "10:00"))
        + run("3", ("서울", "08:30"), ("강릉", "10:30"))
    )
    journey = table.earliest("대전", "강릉", at("06:00"), max_legs=2)[-1]
    assert journey.legs[1].train_no == "3"


def test_staying_on_the_same_train_is_not_a_transfer() -> None:
    table = Timetable(run("101", ("부산", "06:00"), ("동대구", "06:45"), ("대전", "07:40"), ("서울", "08:40")))
    journey = table.earliest("부산", "서울", at("05:00"))[0]
    assert journey.transfers == 0 and journey.duration == timedelta(hours=2, minutes=40)


def test_keeps_direct_and_faster_transfer_as_separate_choices() -> None:
    table = Timetable(
        run("1", ("목포", "07:00"), ("익산", "08:00"))
        + run("2", ("익산", "08:20"), ("서울", "09:30"))
        + run("3", ("목포", "07:05"), ("서울", "10:40"))
    )
    journeys = table.earliest("목포", "서울", at("06:00"), max_legs=2)
    assert [j.transfers for j in journeys] == [0, 1]


def test_options_drop_journeys_that_leave_earlier_for_the_same_arrival() -> None:
    table = Timetable(
        run("1", ("대전", "06:00"), ("오송", "06:20"))
        + run("2", ("대전", "07:00"), ("오송", "07:20"))
        + run("3", ("오송", "08:00"), ("강릉", "11:00"))
    )
    options = table.options("대전", "강릉", at("05:00"), at("12:00"), max_legs=2)
    assert [j.legs[0].train_no for j in options] == ["2"]


def test_future_day_borrows_the_same_weekday() -> None:
    today = date(2026, 11, 13)
    assert sample_day(date(2026, 11, 14), today) == date(2026, 11, 7)
    assert sample_day(date(2026, 11, 20), today) == date(2026, 11, 6)
    assert sample_day(date(2026, 11, 12), today) == date(2026, 11, 12)


def test_rows_become_connections_shifted_to_the_day() -> None:
    rows = [
        {"train": "6", "seq": "2", "station": "서울", "arr": "2026-11-07 08:32:00.0", "dep": ""},
        {"train": "6", "seq": "1", "station": "대전", "arr": "", "dep": "2026-11-07 07:17:00.0"},
    ]
    [c] = connections(rows, timedelta(days=7))
    assert (c.dep, c.arr, c.departs_at, c.arrives_at) == ("대전", "서울", at("07:17"), at("08:32"))


def test_transfer_choice_follows_the_requested_time_of_day() -> None:
    from yeogiro.domain.models import Itinerary, Train, TravelWindow
    from yeogiro.domain.selection import choose_route

    def leg(no: str, dep: str, arr: str, start: str, end: str) -> Train:
        return Train(no, "KTX", dep, arr, at(start), at(end), 10000, None)

    early = Itinerary((leg("1", "대전", "서울", "07:17", "08:32"), leg("2", "서울", "강릉", "08:57", "11:09")))
    late = Itinerary((leg("3", "대전", "서울", "11:26", "12:30"), leg("4", "서울", "강릉", "12:56", "14:56")))
    window = TravelWindow(DAY, datetime.strptime("06:00", "%H:%M").time(), datetime.strptime("12:00", "%H:%M").time(), datetime.strptime("09:00", "%H:%M").time())
    assert choose_route([late, early], window, at("05:00")) is early


def test_transfer_choice_avoids_a_long_wait_on_the_platform() -> None:
    from yeogiro.domain.models import Itinerary, Train, TravelWindow
    from yeogiro.domain.selection import choose_route

    def leg(no: str, dep: str, arr: str, start: str, end: str) -> Train:
        return Train(no, "KTX", dep, arr, at(start), at(end), 10000, None)

    short_wait = Itinerary((leg("144", "대전", "서울", "08:09", "09:20"), leg("809", "서울", "강릉", "09:56", "12:06")))
    long_wait = Itinerary((leg("14", "대전", "서울", "09:07", "10:10"), leg("813", "서울", "강릉", "12:10", "14:14")))
    window = TravelWindow(DAY, datetime.strptime("06:00", "%H:%M").time(), datetime.strptime("12:00", "%H:%M").time(), datetime.strptime("09:00", "%H:%M").time())
    assert choose_route([long_wait, short_wait], window, at("05:00")) is short_wait
