from __future__ import annotations

from datetime import date, datetime, time

from yeogiro.domain.models import Hold, Itinerary, Proposal, Train
from yeogiro.domain.stations import label as station_label

_NATIVE_HOURS = (
    "열두",
    "한",
    "두",
    "세",
    "네",
    "다섯",
    "여섯",
    "일곱",
    "여덟",
    "아홉",
    "열",
    "열한",
)
_DIGITS = ("", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구")
_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")


def sino_number(value: int) -> str:
    if value == 0:
        return "영"
    ten_thousands, rest = divmod(value, 10_000)
    words = []
    if ten_thousands:
        lead = "" if ten_thousands == 1 else _below_ten_thousand(ten_thousands)
        words.append(f"{lead}만")
    if rest:
        words.append(_below_ten_thousand(rest))
    return " ".join(words)


def _below_ten_thousand(value: int) -> str:
    out = ""
    for unit_value, unit in ((1000, "천"), (100, "백"), (10, "십")):
        digit, value = divmod(value, unit_value)
        if digit:
            out += ("" if digit == 1 else _DIGITS[digit]) + unit
    if value:
        out += _DIGITS[value]
    return out


def read_won(amount: int) -> str:
    return f"{sino_number(amount)} 원"


def read_clock(value: time) -> str:
    hour = value.hour
    if hour < 6:
        period = "새벽"
    elif hour < 12:
        period = "오전"
    elif hour < 18:
        period = "오후"
    else:
        period = "저녁"
    spoken = f"{period} {_NATIVE_HOURS[hour % 12]} 시"
    if value.minute:
        spoken += f" {sino_number(value.minute)} 분"
    return spoken


def read_day(day: date, today: date) -> str:
    offset = (day - today).days
    prefix = {0: "오늘 ", 1: "내일 ", 2: "모레 "}.get(offset, "")
    month = f"{day.month}월 " if day.month != today.month else ""
    return f"{prefix}{month}{day.day}일 {_WEEKDAYS[day.weekday()]}요일"


def read_grade(grade: str) -> str:
    return grade.replace("-", " ")


def proposal_sentence(proposal: Proposal, today: date, senior_discounted: bool) -> str:
    itinerary = proposal.itinerary
    if itinerary and len(itinerary.legs) > 1:
        trip = transfer_walkthrough(itinerary, today)
        if itinerary.fare is None:
            return f"{trip} 요금이 확인되지 않아 지금은 예약할 수 없어요."
        people = f"{proposal.party}명 " if proposal.party > 1 else ""
        discount = "경로 할인해서 " if senior_discounted else ""
        tickets = f"표는 두 장이고, {people}{discount}모두 {read_won(proposal.fare_total)}이에요."
        return f"{trip} {tickets} 예약할까요?"
    train = proposal.train
    parts: list[str] = []
    if proposal.sold_out_preferred is not None:
        missed_train = proposal.sold_out_preferred
        if proposal.by_arrival:
            missed = read_clock(missed_train.arrives_at.time())
            parts.append(f"{missed} 도착 기차는 자리가 다 찼어요.")
        else:
            missed = read_clock(missed_train.departs_at.time())
            parts.append(f"{missed} 기차는 자리가 다 찼어요.")

    route_text = f"{read_day(train.departs_at.date(), today)} {train.dep}에서 {train.arr},"
    times = (
        f"{read_grade(train.grade)} {read_clock(train.departs_at.time())} 출발, "
        f"{read_day(train.arrives_at.date(), today) + ' ' if train.arrives_at.date() != train.departs_at.date() else ''}"
        f"{read_clock(train.arrives_at.time())} 도착,"
    )
    people = f" {proposal.party}명" if proposal.party > 1 else ""
    discount = " 경로 할인해서" if senior_discounted else ""
    parts.append(f"{route_text} {times}{people}{discount} {read_won(proposal.fare_total)}이에요.")
    parts.append("예약할까요?")
    if train.fare <= 0:
        return f"{route_description(Itinerary((train,)))} 운임과 좌석은 미확인이에요. 운임 확인 후 예약을 도와드릴게요."
    return " ".join(parts)


def transfer_walkthrough(route: Itinerary, today: date) -> str:
    """A one-transfer journey step by step: where to get off, how long to wait, when it arrives.

    Every leg's own times are read, so the caller hears that the first train reaches the
    transfer station before the second one leaves.
    """
    first, second = route.legs[0], route.legs[-1]

    def when(value: datetime) -> str:
        day = read_day(value.date(), today) + " " if value.date() != first.departs_at.date() else ""
        return day + read_clock(value.time())

    return (
        f"{read_day(first.departs_at.date(), today)} {read_clock(first.departs_at.time())}에 "
        f"{first.dep}에서 타서, {when(first.arrives_at)}에 {first.arr}에서 내리세요. "
        f"{first.arr}에서 {read_duration(route.wait_minutes)} 기다렸다가 "
        f"{when(second.departs_at)} 기차로 갈아타면, {when(second.arrives_at)}에 "
        f"{second.arr}에 도착해요."
    )


def confirm_station(side: str, candidates: tuple[str, ...], one: bool) -> str:
    """Ask which station was meant: yes or no for one, a choice for several."""
    who = "타시는 곳이" if side == "departure" else "가시는 곳이"
    if one or len(candidates) == 1:
        return f"{who} {station_label(candidates[0])} 맞으세요?"
    choices = ", ".join(f"{station_label(c)}이에요" for c in candidates)
    return f"{who} {choices}?"


def route_description(route: Itinerary) -> str:
    """Every train of the journey in spoken form, for when the caller asks for details."""
    day = route.legs[0].departs_at.date()

    def stamp(value: datetime) -> str:
        prefix = f"{value.month}월 {value.day}일 " if value.date() != day else ""
        return prefix + read_clock(value.time())

    spoken: list[str] = []
    for index, train in enumerate(route.legs):
        if index:
            wait = read_duration(route.wait_minutes)
            spoken.append(f"{train.dep}에서 {wait} 기다렸다가")
        order = ("첫 기차 " if index == 0 else "두 번째 기차 ") if len(route.legs) > 1 else ""
        spoken.append(
            f"{order}{read_grade(train.grade)} {stamp(train.departs_at)} {train.dep} 출발, "
            f"{stamp(train.arrives_at)} {train.arr} 도착."
        )
    return " ".join(spoken)


def route_lines(route: Itinerary, holds: tuple[Hold, ...] = ()) -> list[str]:
    """The journey as short text lines for a message."""
    marks = "①②"
    lines: list[str] = []
    for index, train in enumerate(route.legs):
        if index:
            lines.append(
                f"   {train.dep}에서 내려 {route.wait_minutes}분 뒤 {train.departs_at:%H:%M} 열차로 갈아타기"
            )
        seat = f" · {holds[index].seat}" if index < len(holds) and holds[index].seat else ""
        lines.append(
            f"{marks[index]} {train.grade} {train.train_no} {train.departs_at:%H:%M} {train.dep}"
            f" → {train.arrives_at:%H:%M} {train.arr}{seat}"
        )
    return lines


def read_duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    parts = []
    if hours:
        spoken_hours = _NATIVE_HOURS[hours % 12] if hours <= 12 else sino_number(hours)
        parts.append(f"{spoken_hours} 시간")
    if rest:
        parts.append(f"{sino_number(rest)} 분")
    return " ".join(parts) or "영 분"


def proposal_facts(proposal: Proposal, today: date, senior_discounted: bool) -> dict[str, str]:
    if proposal.itinerary and len(proposal.itinerary.legs) > 1:
        route = proposal.itinerary
        first, last = route.legs[0], route.legs[-1]
        return {
            "날짜": read_day(first.departs_at.date(), today),
            "구간": f"{first.dep}에서 {last.arr}",
            "출발": read_clock(first.departs_at.time()),
            "도착": f"{read_day(last.arrives_at.date(), today)} {read_clock(last.arrives_at.time())}",
            "걸리는 시간": read_duration(int(route.duration.total_seconds() // 60)),
            "갈아타는 곳": f"{first.arr}역, {read_duration(route.wait_minutes)} 기다림",
            "요금": (
                f"경로 할인해서 {read_won(proposal.fare_total)}"
                if senior_discounted
                else read_won(proposal.fare_total)
            )
            if route.fare is not None
            else "확인 안 됨",
            "열차": route_description(route),
            "인원": f"{proposal.party}명",
        }
    train = proposal.train
    fare = read_won(proposal.fare_total)
    return {
        "날짜": read_day(train.departs_at.date(), today),
        "구간": f"{train.dep}에서 {train.arr}",
        "출발": read_clock(train.departs_at.time()),
        "도착": read_clock(train.arrives_at.time()),
        "걸리는 시간": read_duration(int(train.duration.total_seconds() // 60)),
        "요금": "미확인"
        if train.fare <= 0
        else f"경로 할인해서 {fare}"
        if senior_discounted
        else fare,
        "열차": f"{read_grade(train.grade)} {sino_number(int(train.train_no))} 번",
        "인원": f"{proposal.party}명",
        "좌석": "재고 미확인" if train.seats_available is None else "일반실",
    }


def reconfirm_route(route: Itinerary, by_arrival: bool = False) -> str:
    if route.fare is None:
        return "요금을 확인하지 못해서 지금은 예약할 수 없어요. 다른 시간으로 찾아볼까요?"
    if len(route.legs) == 1:
        return reconfirm_sentence(route.legs[0], by_arrival)
    first, last = route.legs[0], route.legs[-1]
    return (
        f"{read_clock(first.departs_at.time())}에 {first.dep}에서 타서 {first.arr}에서 "
        f"{read_clock(last.departs_at.time())} 기차로 갈아타서, "
        f"{read_clock(last.arrives_at.time())}에 {last.arr} 도착하는 기차예요. 예약할까요?"
    )


def reconfirm_sentence(train: Train, by_arrival: bool = False) -> str:
    departs = read_clock(train.departs_at.time())
    if by_arrival:
        arrives = read_clock(train.arrives_at.time())
        return f"{departs}에 출발해서 {arrives}에 {train.arr} 도착하는 기차예요. 예약할까요?"
    return f"{departs}에 {train.arr} 가는 기차예요. 예약할까요?"


def ticket_message(hold: Hold, party: int) -> str:
    if hold.itinerary and hold.leg_holds:
        first = hold.itinerary.legs[0]
        last = hold.itinerary.legs[-1]
        people = f" · {party}명" if party > 1 else ""
        return "\n".join(
            [
                "[여기로] 예약 확인 · 환승 1회",
                f"{first.departs_at.month}월 {first.departs_at.day}일"
                f"({_WEEKDAYS[first.departs_at.weekday()]}) {first.dep}→{last.arr}",
                *route_lines(hold.itinerary, hold.leg_holds),
                f"{hold.fare_total:,}원{people}",
                f"예약번호 {' · '.join(h.pnr for h in hold.leg_holds)}",
                "체험용 예약입니다. 실제 결제는 되지 않았고 곧 자동 취소됩니다.",
            ]
        )
    train = hold.train
    weekday = _WEEKDAYS[train.departs_at.weekday()]
    seat = f"{hold.seat} · " if hold.seat else ""
    people = f" · {party}명" if party > 1 else ""
    lines = [
        "[여기로] 예약 확인",
        f"{train.departs_at.month}월 {train.departs_at.day}일({weekday}) {train.dep}→{train.arr}",
        f"{train.grade} {train.train_no} {train.departs_at:%H:%M} 출발 · "
        f"{train.arrives_at:%H:%M} 도착",
        f"{seat}{hold.fare_total:,}원{people}",
        f"예약번호 {hold.pnr}",
        "체험용 예약입니다. 실제 결제는 되지 않았고 곧 자동 취소됩니다.",
    ]
    return "\n".join(lines)
