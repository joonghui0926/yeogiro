from __future__ import annotations

from datetime import date, datetime, time

from yeogiro.domain.models import Hold, Itinerary, Proposal, Train

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
        route = itinerary
        fare = read_won(proposal.fare_total) if route.fare is not None else "일부 구간 운임 미확인"
        return (
            f"{read_day(route.legs[0].departs_at.date(), today)} "
            f"{route_description(route)} {proposal.party}명 예상 합계 {fare}이에요. "
            "좌석 재고는 확인되지 않았어요. 각 열차를 별도로 모의 예약하며 실제 결제는 없어요. "
            "두 구간 모두 이 여정으로 모의 예약할까요?"
        )
    train = proposal.train
    parts: list[str] = []
    if proposal.sold_out_preferred is not None:
        missed = read_clock(proposal.sold_out_preferred.departs_at.time())
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
    if train.seats_available is None:
        parts.insert(-1, "시간표 기준 안내이며 좌석 재고는 확인되지 않았어요.")
    if train.fare <= 0:
        return f"{route_description(Itinerary((train,)))} 운임과 좌석은 미확인이에요. 운임 확인 후 예약을 도와드릴게요."
    return " ".join(parts)


def route_description(route: Itinerary) -> str:
    day = route.legs[0].departs_at.date()

    def stamp(value: datetime) -> str:
        prefix = f"{value.month}월 {value.day}일 " if value.date() != day else ""
        return prefix + read_clock(value.time())

    legs = [
        f"{index}번째 열차 {read_grade(t.grade)} {t.train_no}번, {t.dep}에서 "
        f"{stamp(t.departs_at)} 출발, {t.arr}에 {stamp(t.arrives_at)} 도착."
        for index, t in enumerate(route.legs, 1)
    ]
    transfer = (
        (
            f"{route.legs[0].arr}역에서 한 번 갈아타며 "
            f"환승 대기 {read_duration(route.wait_minutes)}이에요. "
        )
        if len(route.legs) > 1
        else ""
    )
    return (
        transfer
        + " ".join(legs)
        + f" 전체 소요시간 {read_duration(int(route.duration.total_seconds() // 60))}이에요."
    )


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
        return {
            "날짜": read_day(route.legs[0].departs_at.date(), today),
            "구간": f"{route.legs[0].dep}에서 {route.legs[-1].arr}",
            "출발": read_clock(route.legs[0].departs_at.time()),
            "도착": f"{read_day(route.legs[-1].arrives_at.date(), today)} {read_clock(route.legs[-1].arrives_at.time())}",
            "걸리는 시간": read_duration(int(route.duration.total_seconds() // 60)),
            "요금": f"예상 합계 {read_won(proposal.fare_total)}"
            if route.fare is not None
            else "일부 구간 운임 미확인",
            "열차": route_description(route),
            "인원": f"{proposal.party}명",
            "좌석": "재고 미확인",
            "예약": "각 구간 별도 모의 예약, 실제 결제 없음",
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


def reconfirm_sentence(train: Train) -> str:
    return f"{read_clock(train.departs_at.time())}에 {train.arr} 가는 기차예요. 예약할까요?"


def ticket_message(hold: Hold, party: int) -> str:
    if hold.itinerary and hold.leg_holds:
        return "\n".join(
            [
                "[여기로] 환승 여정 모의 예약 확인 · 구간별 별도 예약",
                route_description(hold.itinerary),
                *(
                    f"{i}구간 {h.train.dep}→{h.train.arr} · 예약번호 {h.pnr} · {h.seat} · {h.fare_total:,}원"
                    for i, h in enumerate(hold.leg_holds, 1)
                ),
                f"{party}명 합계 {hold.fare_total:,}원",
                "체험용입니다. 실제 좌석 확보·발권·결제는 되지 않았습니다.",
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
