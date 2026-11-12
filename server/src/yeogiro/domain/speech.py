from __future__ import annotations

from datetime import date, time

from yeogiro.domain.models import Hold, Proposal, Train

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
    train = proposal.train
    parts: list[str] = []
    if proposal.sold_out_preferred is not None:
        missed = read_clock(proposal.sold_out_preferred.departs_at.time())
        parts.append(f"{missed} 기차는 자리가 다 찼어요.")

    route = f"{read_day(train.departs_at.date(), today)} {train.dep}에서 {train.arr},"
    times = (
        f"{read_grade(train.grade)} {read_clock(train.departs_at.time())} 출발, "
        f"{read_clock(train.arrives_at.time())} 도착,"
    )
    people = f" {proposal.party}명" if proposal.party > 1 else ""
    discount = " 경로 할인해서" if senior_discounted else ""
    parts.append(f"{route} {times}{people}{discount} {read_won(proposal.fare_total)}이에요.")
    parts.append("예약할까요?")
    return " ".join(parts)


def read_duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{_NATIVE_HOURS[hours % 12]} 시간")
    if rest:
        parts.append(f"{sino_number(rest)} 분")
    return " ".join(parts) or "영 분"


def proposal_facts(proposal: Proposal, today: date, senior_discounted: bool) -> dict[str, str]:
    train = proposal.train
    fare = read_won(proposal.fare_total)
    return {
        "날짜": read_day(train.departs_at.date(), today),
        "구간": f"{train.dep}에서 {train.arr}",
        "출발": read_clock(train.departs_at.time()),
        "도착": read_clock(train.arrives_at.time()),
        "걸리는 시간": read_duration(int(train.duration.total_seconds() // 60)),
        "요금": f"경로 할인해서 {fare}" if senior_discounted else fare,
        "열차": f"{read_grade(train.grade)} {sino_number(int(train.train_no))} 번",
        "인원": f"{proposal.party}명",
        "좌석": "일반실",
    }


def reconfirm_sentence(train: Train) -> str:
    return f"{read_clock(train.departs_at.time())}에 {train.arr} 가는 기차예요. 예약할까요?"


def ticket_message(hold: Hold, party: int) -> str:
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
