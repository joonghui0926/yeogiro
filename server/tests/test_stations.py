from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from test_session_drop_trip import make_session

from yeogiro.calls import lines
from yeogiro.config import KST
from yeogiro.domain import speech, stations
from yeogiro.domain.models import Itinerary, Train
from yeogiro.domain.stations import label, match, sounds_alike


class TestMatch:
    def test_plain_station_needs_no_question(self) -> None:
        found = match("서울역")
        assert (found.station, found.certain) == ("서울", True)

    def test_covers_stations_beyond_the_old_short_list(self) -> None:
        for name in ("정동진", "남원", "안동", "군산", "춘천", "울진", "부전"):
            assert stations.is_supported(name), name

    @pytest.mark.parametrize(
        ("heard", "alike"),
        [("대전", "대천"), ("전주", "진주"), ("경주", "광주"), ("청주", "충주"), ("춘천", "순천")],
    )
    def test_alike_names_are_confirmed(self, heard: str, alike: str) -> None:
        found = match(heard)
        assert found.station == heard and not found.certain
        assert found.candidates[0] == heard and alike in found.candidates

    def test_city_with_several_stations_offers_a_choice(self) -> None:
        found = match("대구")
        assert found.station is None
        assert found.candidates == ("동대구", "대구", "서대구")

    def test_misheard_name_is_offered_back(self) -> None:
        found = match("동대규")
        assert found.station is None and found.candidates[0] == "동대구"

    def test_aliases_and_places_without_trains(self) -> None:
        assert match("여수").station == "여수엑스포"
        assert match("신경주역").station == "경주"
        assert match("제주").candidates == ()

    def test_live_directory_names_become_speakable(self) -> None:
        assert not stations.is_supported("가상역테스트")
        stations.register(["가상역테스트", "Bad Name", "김천(구미)"])
        assert stations.is_supported("가상역테스트") and not stations.is_supported("Bad Name")
        assert stations.is_supported("김천구미")

    def test_label_reads_the_province_only_for_a_do(self) -> None:
        assert label("진주") == "경상남도 진주역"
        assert label("동대구") == "동대구역"
        assert label("서울") == "서울역"

    def test_sounds_alike_is_about_pronunciation(self) -> None:
        assert sounds_alike("대전", "대천") and not sounds_alike("서울", "부산")


async def test_departure_is_always_asked_even_with_a_home_station() -> None:
    session, _, _, _ = make_session()  # tester's home station is 대전
    result = await session._find_trains({"arrival": "부산", "relative_day": "tomorrow"})
    assert result == {"need": "departure", "say": lines.ASK_DEPARTURE}


async def test_alike_station_is_confirmed_once_then_date_is_asked() -> None:
    session, _, _, _ = make_session()
    asked = await session._find_trains({"departure": "서울", "arrival": "진주"})
    assert asked["need"] == "confirm_station" and asked["side"] == "arrival"
    assert asked["say"] == "가시는 곳이 경상남도 진주역 맞으세요?"
    assert "전주" in asked["candidates"]

    confirmed = await session._find_trains(
        {"departure": "서울", "arrival": "진주", "confirmed_stations": ["진주"]}
    )
    assert confirmed == {"need": "date", "say": lines.ASK_DATE}
    # Once confirmed, the same station is not asked again in this call.
    again = await session._find_trains({"departure": "서울", "arrival": "진주"})
    assert again["need"] == "date"


async def test_station_questions_go_departure_first_and_offer_choices() -> None:
    session, _, _, _ = make_session()
    asked = await session._find_trains({"departure": "대구", "arrival": "전주"})
    assert asked["side"] == "departure"
    assert asked["say"] == "타시는 곳이 동대구역이에요, 대구역이에요, 서대구역이에요?"


async def test_unknown_and_same_station() -> None:
    session, _, _, _ = make_session()
    unknown = await session._find_trains({"departure": "서울", "arrival": "제주"})
    assert unknown == {"need": "arrival", "say": lines.STATION_NOT_FOUND["arrival"]}
    same = await session._find_trains({"departure": "서울", "arrival": "서울역"})
    assert same == {"need": "arrival", "say": lines.SAME_STATION}


def _leg(no: str, dep: str, arr: str, start: time, minutes: int) -> Train:
    departs = datetime.combine(date(2099, 11, 17), start, KST)
    return Train(no, "KTX", dep, arr, departs, departs + timedelta(minutes=minutes), 10000, None)


def test_second_train_must_leave_after_the_first_arrives() -> None:
    first = _leg("1", "서울", "동대구", time(9), 100)  # arrives 10:40
    with pytest.raises(ValueError):
        Itinerary((first, _leg("2", "동대구", "진주", time(10, 30), 90)))
    Itinerary((first, _leg("2", "동대구", "진주", time(11), 90)))


def test_transfer_walkthrough_reads_every_step() -> None:
    route = Itinerary(
        (_leg("1", "서울", "동대구", time(9), 100), _leg("2", "동대구", "진주", time(11), 90))
    )
    said = speech.transfer_walkthrough(route, date(2099, 11, 16))
    assert said == (
        "내일 17일 화요일 오전 아홉 시에 서울에서 타서, 오전 열 시 사십 분에 동대구에서 내리세요. "
        "동대구에서 이십 분 기다렸다가 오전 열한 시 기차로 갈아타면, "
        "오후 열두 시 삼십 분에 진주에 도착해요."
    )
    short = speech.reconfirm_route(route)
    assert short == (
        "오전 아홉 시에 서울에서 타서 동대구에서 오전 열한 시 기차로 갈아타서, "
        "오후 열두 시 삼십 분에 진주 도착하는 기차예요. 예약할까요?"
    )
