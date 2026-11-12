from __future__ import annotations

from yeogiro.domain.models import Train

SENIOR_DISCOUNT_PERCENT = 30


def senior_discount_applies(train: Train) -> bool:
    return train.departs_at.weekday() < 5


def fare_total(train: Train, party: int, senior: bool) -> int:
    caller_fare = train.fare
    if senior and senior_discount_applies(train):
        discounted = train.fare * (100 - SENIOR_DISCOUNT_PERCENT) // 100
        caller_fare = discounted - discounted % 100
    return caller_fare + train.fare * max(party - 1, 0)
