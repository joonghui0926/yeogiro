from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum

from yeogiro.domain.models import TravelWindow


class RelativeDay(StrEnum):
    TODAY = "today"
    TOMORROW = "tomorrow"
    DAY_AFTER_TOMORROW = "day_after_tomorrow"
    THIS_WEEK = "this_week"
    NEXT_WEEK = "next_week"
    DATE = "date"
    UNSPECIFIED = "unspecified"


class PartOfDay(StrEnum):
    DAWN = "dawn"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    ANY = "any"


WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_PARTS: dict[PartOfDay, tuple[time, time, time]] = {
    PartOfDay.DAWN: (time(5, 0), time(8, 0), time(6, 30)),
    PartOfDay.MORNING: (time(6, 0), time(12, 0), time(9, 0)),
    PartOfDay.NOON: (time(11, 0), time(14, 0), time(12, 30)),
    PartOfDay.AFTERNOON: (time(12, 0), time(18, 0), time(15, 0)),
    PartOfDay.EVENING: (time(17, 0), time(21, 0), time(19, 0)),
    PartOfDay.NIGHT: (time(19, 0), time(23, 59), time(21, 0)),
    PartOfDay.ANY: (time(5, 0), time(23, 59), time(10, 0)),
}

BOOKING_LEAD = timedelta(minutes=20)


def resolve_day(
    relative: RelativeDay,
    weekday: str | None,
    month: int | None,
    day_of_month: int | None,
    today: date,
) -> date | None:
    target_weekday = WEEKDAYS.index(weekday) if weekday in WEEKDAYS else None

    if relative is RelativeDay.TODAY:
        return today
    if relative is RelativeDay.TOMORROW:
        return today + timedelta(days=1)
    if relative is RelativeDay.DAY_AFTER_TOMORROW:
        return today + timedelta(days=2)
    if relative is RelativeDay.NEXT_WEEK and target_weekday is not None:
        next_monday = today + timedelta(days=7 - today.weekday())
        return next_monday + timedelta(days=target_weekday)
    if day_of_month is not None:
        return _next_calendar_day(month, day_of_month, today)
    if target_weekday is not None:
        ahead = (target_weekday - today.weekday()) % 7
        return today + timedelta(days=ahead)
    return None


def _next_calendar_day(month: int | None, day_of_month: int, today: date) -> date | None:
    candidates: list[tuple[int, int]] = []
    if month is not None:
        candidates = [(today.year, month), (today.year + 1, month)]
    else:
        next_month_year = today.year + (1 if today.month == 12 else 0)
        next_month = 1 if today.month == 12 else today.month + 1
        candidates = [(today.year, today.month), (next_month_year, next_month)]
    for year, candidate_month in candidates:
        try:
            candidate = date(year, candidate_month, day_of_month)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return None


def resolve_window(
    day: date,
    part: PartOfDay,
    clock: str | None,
    now: datetime,
) -> TravelWindow:
    start, end, center = _PARTS[part]
    asked = _parse_clock(clock, part)
    if asked is not None:
        center = asked
        start = _shift(asked, -45)
        end = _shift(asked, 75)

    if day == now.date():
        earliest = (now + BOOKING_LEAD).time().replace(second=0, microsecond=0)
        if earliest > start:
            start = earliest
        if start >= end:
            end = _shift(start, 180)
        if center < start:
            center = start

    return TravelWindow(day=day, start=start, end=end, center=center)


def _parse_clock(value: str | None, part: PartOfDay) -> time | None:
    if not value:
        return None
    try:
        hour_text, minute_text = value.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    afternoon_parts = {PartOfDay.AFTERNOON, PartOfDay.EVENING, PartOfDay.NIGHT}
    if (hour < 12 and part in afternoon_parts) or (
        1 <= hour <= 6 and part in {PartOfDay.ANY, PartOfDay.NOON}
    ):
        hour += 12
    return time(hour, minute)


def _shift(value: time, minutes: int) -> time:
    anchor = datetime.combine(date(2000, 1, 1), value) + timedelta(minutes=minutes)
    if anchor.date() < date(2000, 1, 1):
        return time(0, 0)
    if anchor.date() > date(2000, 1, 1):
        return time(23, 59)
    return anchor.time()
