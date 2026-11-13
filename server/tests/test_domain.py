from __future__ import annotations

from datetime import date, datetime, time, timedelta

from yeogiro.adapters.rail.mock import build_timetable
from yeogiro.config import KST
from yeogiro.domain import consent, fares, speech
from yeogiro.domain.models import Hold, Proposal, Train, TravelWindow
from yeogiro.domain.selection import adjacent_train, choose_train
from yeogiro.domain.when import PartOfDay, RelativeDay, resolve_day, resolve_window

THURSDAY = date(2026, 11, 12)


def train(hour: int, minute: int, seats: bool = True, minutes: int = 64) -> Train:
    departs = datetime.combine(THURSDAY + timedelta(days=5), time(hour, minute), KST)
    return Train(
        "119", "KTX", "대전", "서울", departs, departs + timedelta(minutes=minutes), 23700, seats
    )


class TestResolveDay:
    def test_next_week_tuesday(self) -> None:
        assert resolve_day(RelativeDay.NEXT_WEEK, "tue", None, None, THURSDAY) == date(2026, 11, 17)

    def test_tomorrow(self) -> None:
        assert resolve_day(RelativeDay.TOMORROW, None, None, None, THURSDAY) == date(2026, 11, 13)

    def test_bare_weekday_is_next_occurrence(self) -> None:
        assert resolve_day(RelativeDay.UNSPECIFIED, "mon", None, None, THURSDAY) == date(
            2026, 11, 16
        )

    def test_day_of_month_rolls_to_next_month_when_past(self) -> None:
        assert resolve_day(RelativeDay.DATE, None, None, 3, THURSDAY) == date(2026, 12, 3)

    def test_nothing_known(self) -> None:
        assert resolve_day(RelativeDay.UNSPECIFIED, None, None, None, THURSDAY) is None


class TestResolveWindow:
    def test_four_oclock_means_afternoon(self) -> None:
        now = datetime.combine(THURSDAY, time(9, 0), KST)
        window = resolve_window(THURSDAY + timedelta(days=1), PartOfDay.ANY, "04:00", now)
        assert window.center == time(16, 0)

    def test_today_starts_after_booking_lead(self) -> None:
        now = datetime.combine(THURSDAY, time(14, 50), KST)
        window = resolve_window(THURSDAY, PartOfDay.AFTERNOON, None, now)
        assert window.start == time(15, 10)


class TestChooseTrain:
    def test_closest_to_center(self) -> None:
        window = TravelWindow(THURSDAY + timedelta(days=5), time(12), time(18), time(15))
        trains = [train(13, 0), train(14, 50), train(16, 30)]
        choice = choose_train(trains, window, datetime(2026, 11, 12, tzinfo=KST))
        assert choice is not None and choice.train.departs_at.time() == time(14, 50)

    def test_sold_out_offers_nearest_with_seats(self) -> None:
        window = TravelWindow(THURSDAY + timedelta(days=5), time(15), time(17), time(16, 24))
        trains = [train(16, 24, seats=False), train(15, 0), train(18, 8)]
        choice = choose_train(trains, window, datetime(2026, 11, 12, tzinfo=KST))
        assert choice is not None
        assert choice.sold_out_preferred is not None
        assert choice.train.departs_at.time() == time(15, 0)

    def test_forced_sold_out(self) -> None:
        window = TravelWindow(THURSDAY + timedelta(days=5), time(12), time(18), time(15))
        trains = [train(15, 0), train(15, 40)]
        choice = choose_train(trains, window, datetime(2026, 11, 12, tzinfo=KST), True)
        assert choice is not None and choice.train.departs_at.time() == time(15, 40)


class TestAskedTime:
    """A named departure or arrival time: at or before it first, then the closest."""

    day = THURSDAY + timedelta(days=5)
    now = datetime(2026, 11, 12, tzinfo=KST)

    def window(self, asked: time, anchor: str = "departs") -> TravelWindow:
        return TravelWindow(self.day, time(5), time(23, 59), asked, asked, anchor)  # type: ignore[arg-type]

    def test_arrival_time_alone_resolves(self) -> None:
        now = datetime.combine(THURSDAY, time(9, 0), KST)
        window = resolve_window(self.day, PartOfDay.ANY, None, now, "04:00")
        assert window.asked == time(16, 0)
        assert window.anchor == "arrives"
        assert window.start <= time(10, 0) and window.end == time(16, 0)

    def test_arrival_wins_when_both_given(self) -> None:
        now = datetime.combine(THURSDAY, time(9, 0), KST)
        window = resolve_window(self.day, PartOfDay.AFTERNOON, "01:00", now, "05:00")
        assert (window.asked, window.anchor) == (time(17, 0), "arrives")

    def test_departure_prefers_earlier_over_closer_later(self) -> None:
        trains = [train(14, 40), train(15, 5), train(9, 0), train(10, 0)]
        choice = choose_train(trains, self.window(time(15)), self.now)
        assert choice is not None and choice.train.departs_at.time() == time(14, 40)
        assert not choice.by_arrival

    def test_closest_earlier_beats_many_early_trains(self) -> None:
        trains = [train(h, 0) for h in range(6, 14)] + [train(14, 30)]
        choice = choose_train(trains, self.window(time(15)), self.now)
        assert choice is not None and choice.train.departs_at.time() == time(14, 30)

    def test_departure_falls_back_to_closest_later(self) -> None:
        trains = [train(15, 40), train(15, 10), train(18, 0)]
        choice = choose_train(trains, self.window(time(15)), self.now)
        assert choice is not None and choice.train.departs_at.time() == time(15, 10)

    def test_arrival_ranks_by_arrival_time(self) -> None:
        # 13:00 KTX arrives 14:04, 12:50 slow train arrives 15:20, 14:00 KTX arrives 15:04.
        trains = [train(13, 0), train(12, 50, minutes=150), train(14, 0)]
        choice = choose_train(trains, self.window(time(15), "arrives"), self.now)
        assert choice is not None
        assert choice.train.arrives_at.time() == time(14, 4)
        assert choice.by_arrival

    def test_arrival_prefers_the_latest_train_that_still_makes_it(self) -> None:
        # Real 대전→서울 case: a 무궁화 leaving 13:57 arrives 15:59, a KTX leaving 14:50 arrives 15:47.
        trains = [train(13, 57, minutes=122), train(14, 50, minutes=57)]
        choice = choose_train(trains, self.window(time(16), "arrives"), self.now)
        assert choice is not None and choice.train.departs_at.time() == time(14, 50)

    def test_arrival_sold_out_keeps_the_same_rule(self) -> None:
        trains = [train(13, 50, seats=False), train(12, 0), train(13, 0), train(15, 0)]
        choice = choose_train(trains, self.window(time(15), "arrives"), self.now)
        assert choice is not None and choice.sold_out_preferred is not None
        assert choice.sold_out_preferred.departs_at.time() == time(13, 50)
        assert choice.train.departs_at.time() == time(13, 0)

    def test_transfer_route_ranks_by_final_arrival(self) -> None:
        from yeogiro.domain.models import Itinerary
        from yeogiro.domain.selection import choose_route

        def leg(dep: str, arr: str, h: int, m: int, minutes: int) -> Train:
            departs = datetime.combine(self.day, time(h, m), KST)
            return Train("1", "KTX", dep, arr, departs, departs + timedelta(minutes=minutes), 1, True)

        early = Itinerary((leg("A", "B", 9, 0, 60), leg("B", "C", 10, 30, 60)))  # 11:30
        close = Itinerary((leg("A", "B", 12, 0, 60), leg("B", "C", 13, 20, 60)))  # 14:20
        late = Itinerary((leg("A", "B", 13, 0, 60), leg("B", "C", 14, 10, 60)))  # 15:10
        picked = choose_route([early, late, close], self.window(time(15), "arrives"), self.now)
        assert picked is close

    def test_respects_booking_lead(self) -> None:
        now = datetime.combine(self.day, time(14, 50), KST)
        trains = [train(14, 30), train(15, 30)]
        choice = choose_train(trains, self.window(time(15)), now)
        assert choice is not None and choice.train.departs_at.time() == time(15, 30)


class TestSpeech:
    def test_won(self) -> None:
        assert speech.read_won(13020) == "만 삼천이십 원"
        assert speech.read_won(23700) == "이만 삼천칠백 원"

    def test_clock(self) -> None:
        assert speech.read_clock(time(14, 6)) == "오후 두 시 육 분"
        assert speech.read_clock(time(18, 0)) == "저녁 여섯 시"
        assert speech.read_clock(time(9, 30)) == "오전 아홉 시 삼십 분"

    def test_proposal(self) -> None:
        proposal = Proposal("opt", train(14, 6), 1, False, 23700, None, datetime.now(KST))
        text = speech.proposal_sentence(proposal, THURSDAY, False)
        assert text == (
            "17일 화요일 대전에서 서울, KTX 오후 두 시 육 분 출발, 오후 세 시 십 분 도착, "
            "이만 삼천칠백 원이에요. 예약할까요?"
        )

    def test_arrival_proposal_reads_both_times(self) -> None:
        proposal = Proposal(
            "opt", train(14, 6), 1, False, 23700, None, datetime.now(KST), by_arrival=True
        )
        text = speech.proposal_sentence(proposal, THURSDAY, False)
        assert "오후 두 시 육 분 출발" in text and "오후 세 시 십 분 도착" in text
        assert speech.reconfirm_sentence(proposal.train, True) == (
            "오후 두 시 육 분에 출발해서 오후 세 시 십 분에 서울 도착하는 기차예요. 예약할까요?"
        )

    def test_arrival_sold_out_names_arrival_time(self) -> None:
        proposal = Proposal(
            "opt",
            train(13, 0),
            1,
            False,
            23700,
            train(13, 50, seats=False),
            datetime.now(KST),
            by_arrival=True,
        )
        text = speech.proposal_sentence(proposal, THURSDAY, False)
        assert text.startswith("오후 두 시 오십사 분 도착 기차는 자리가 다 찼어요.")

    def test_ticket_message_has_no_link(self) -> None:
        hold = Hold("12345678", train(14, 6), 23700, "3호차 7A", None, "mock")
        body = speech.ticket_message(hold, 1)
        assert body.startswith("[여기로] 예약 확인")
        assert "http" not in body


class TestFares:
    def test_senior_weekday(self) -> None:
        assert fares.fare_total(train(14, 6), 1, senior=True) == 16500

    def test_senior_weekend_pays_full(self) -> None:
        weekend = train(14, 6)
        saturday = Train(
            weekend.train_no,
            weekend.grade,
            weekend.dep,
            weekend.arr,
            weekend.departs_at - timedelta(days=3),
            weekend.arrives_at - timedelta(days=3),
            weekend.fare,
            True,
        )
        assert fares.fare_total(saturday, 1, senior=True) == 23700


class TestGate:
    def base(self, **overrides: object) -> consent.GateInput:
        values: dict[str, object] = {
            "option_is_latest": True,
            "option_age_seconds": 20.0,
            "proposal_heard": True,
            "verdict": consent.Verdict.YES,
            "tester_registered": True,
            "holds_today": 0,
            "active_holds": 0,
            "minutes_to_departure": 300.0,
            "duplicate_hold": False,
            "booking_enabled": True,
        }
        values.update(overrides)
        return consent.GateInput(**values)  # type: ignore[arg-type]

    def test_all_pass(self) -> None:
        assert consent.evaluate(self.base()).passed

    def test_unclear_reply_blocks(self) -> None:
        decision = consent.evaluate(self.base(verdict=consent.Verdict.UNCLEAR))
        assert decision.failed_codes == ("consent",)

    def test_stale_option_blocks(self) -> None:
        assert not consent.evaluate(self.base(option_age_seconds=200.0)).passed

    def test_switch_off_blocks(self) -> None:
        assert consent.evaluate(self.base(booking_enabled=False)).failed_codes == ("switch",)


def test_mock_timetable_is_stable() -> None:
    first = build_timetable("대전", "서울", THURSDAY)
    assert first == build_timetable("대전", "서울", THURSDAY)
    assert all(t.arrives_at > t.departs_at for t in first)




def numbered(no: str, hour: int, seats: bool = True) -> Train:
    departs = datetime.combine(THURSDAY + timedelta(days=5), time(hour, 0), KST)
    return Train(no, "KTX", "대전", "서울", departs, departs + timedelta(minutes=64), 23700, seats)


class TestAdjacent:
    def test_later_and_earlier(self) -> None:
        trains = [
            numbered("101", 14),
            numbered("103", 15),
            numbered("105", 16, seats=False),
            numbered("107", 17),
        ]
        now = datetime(2026, 11, 12, tzinfo=KST)
        later = adjacent_train(trains, trains[1], "later", now)
        assert later is not None and later.departs_at.time() == time(17, 0)  # 16:00 sold out
        earlier = adjacent_train(trains, trains[1], "earlier", now)
        assert earlier is not None and earlier.departs_at.time() == time(14, 0)

    def test_none_when_edge(self) -> None:
        trains = [numbered("101", 14), numbered("103", 15)]
        now = datetime(2026, 11, 12, tzinfo=KST)
        assert adjacent_train(trains, trains[0], "earlier", now) is None


class TestSpeechExtra:
    def test_duration(self) -> None:
        assert speech.read_duration(64) == "한 시간 사 분"
        assert speech.read_duration(100) == "한 시간 사십 분"
        assert speech.read_duration(45) == "사십오 분"

    def test_proposal_facts_keys(self) -> None:
        proposal = Proposal("opt", train(14, 6), 1, True, 16500, None, datetime.now(KST))
        facts = speech.proposal_facts(proposal, THURSDAY, True)
        assert facts["출발"] == "오후 두 시 육 분"
        assert "경로 할인해서" in facts["요금"]
        assert facts["도착"] == "오후 세 시 십 분"


class TestRideTime:
    def test_prefers_fast_train_over_slow_local_at_exact_time(self) -> None:
        day = THURSDAY + timedelta(days=3)

        def make(no: str, grade: str, hour: int, minute: int, ride: int) -> Train:
            departs = datetime.combine(day, time(hour, minute), KST)
            return Train(no, grade, "대전", "부산", departs, departs + timedelta(minutes=ride), 26500, True)

        local = make("1201", "무궁화호", 8, 59, 234)
        ktx = make("103", "KTX", 9, 20, 98)
        window = TravelWindow(day, time(6), time(12), time(9))
        choice = choose_train([local, ktx], window, datetime(2026, 11, 13, tzinfo=KST))
        assert choice is not None and choice.train.grade == "KTX"

    def test_exact_time_still_wins_between_similar_trains(self) -> None:
        trains = [numbered("101", 14), numbered("103", 15), numbered("105", 16)]
        window = TravelWindow(THURSDAY + timedelta(days=5), time(12), time(18), time(15))
        choice = choose_train(trains, window, datetime(2026, 11, 12, tzinfo=KST))
        assert choice is not None and choice.train.train_no == "103"
