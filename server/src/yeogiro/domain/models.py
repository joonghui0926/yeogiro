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
    seats_available: bool | None

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
    itinerary: Itinerary | None = None


@dataclass(frozen=True, slots=True)
class Proposal:
    option_id: str
    train: Train
    party: int
    senior: bool
    fare_total: int
    sold_out_preferred: Train | None
    created_at: datetime
    itinerary: Itinerary | None = None


@dataclass(frozen=True, slots=True)
class Hold:
    pnr: str
    train: Train
    fare_total: int
    seat: str | None
    pay_by: datetime | None
    provider: str
    itinerary: Itinerary | None = None
    leg_holds: tuple[Hold, ...] = ()


@dataclass(frozen=True, slots=True)
class Itinerary:
    legs: tuple[Train, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.legs) <= 2:
            raise ValueError("only direct and one-transfer itineraries are supported")
        if any(t.duration <= timedelta() for t in self.legs):
            raise ValueError("invalid train times")
        if len(self.legs) == 2:
            first, second = self.legs
            if first.arr != second.dep or first.arrives_at >= second.departs_at:
                raise ValueError("disconnected itinerary")

    @property
    def key(self) -> str:
        return "|".join(t.key for t in self.legs)

    @property
    def duration(self) -> timedelta:
        return self.legs[-1].arrives_at - self.legs[0].departs_at

    @property
    def fare(self) -> int | None:
        return sum(t.fare for t in self.legs) if all(t.fare > 0 for t in self.legs) else None

    @property
    def wait_minutes(self) -> int:
        if len(self.legs) == 1:
            return 0
        return int((self.legs[1].departs_at - self.legs[0].arrives_at).total_seconds() // 60)
