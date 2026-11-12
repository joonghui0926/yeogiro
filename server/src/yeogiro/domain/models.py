from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class Train:
    train_no: str
    grade: str
    dep: str
    arr: str
    departs_at: datetime
    arrives_at: datetime
    fare: int
    seats_available: bool

    @property
    def duration(self) -> timedelta:
        return self.arrives_at - self.departs_at

    @property
    def key(self) -> str:
        return f"{self.departs_at:%Y%m%d}-{self.train_no}-{self.dep}-{self.arr}"


@dataclass(frozen=True, slots=True)
class TravelWindow:
    day: date
    start: time
    end: time
    center: time


@dataclass(frozen=True, slots=True)
class Choice:
    train: Train
    sold_out_preferred: Train | None


@dataclass(frozen=True, slots=True)
class Proposal:
    option_id: str
    train: Train
    party: int
    senior: bool
    fare_total: int
    sold_out_preferred: Train | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Hold:
    pnr: str
    train: Train
    fare_total: int
    seat: str | None
    pay_by: datetime | None
    provider: str
