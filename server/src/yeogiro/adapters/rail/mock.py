from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from yeogiro.config import KST
from yeogiro.domain.models import Hold, Train
from yeogiro.domain.stations import CONVENTIONAL_ONLY, KTX_MINUTES_FROM_SEOUL
from yeogiro.ports import HoldRequest

_HEADWAYS = (22, 28, 34, 41, 47, 55)
_FIRST_DEPARTURE = time(5, 10)
_LAST_DEPARTURE = time(22, 40)


class MockRail:
    name = "mock"

    async def search(self, dep: str, arr: str, day: date) -> list[Train]:
        return build_timetable(dep, arr, day)

    async def hold(self, request: HoldRequest) -> Hold:
        rng = random.Random(f"{request.call_id}{request.train.key}")
        car = rng.randint(2, 16)
        seat = f"{rng.randint(1, 15)}{rng.choice('ABCD')}"
        return Hold(
            pnr=f"{rng.randint(1000, 9999)}{rng.randint(1000, 9999)}",
            train=request.train,
            fare_total=request.fare_total,
            seat=f"{car}호차 {seat}",
            pay_by=datetime.now(KST) + timedelta(minutes=10),
            provider=self.name,
        )

    async def cancel(self, hold: Hold) -> None:
        return None


def build_timetable(dep: str, arr: str, day: date) -> list[Train]:
    rng = random.Random(f"{dep}>{arr}@{day.isoformat()}")
    distance = abs(KTX_MINUTES_FROM_SEOUL.get(dep, 60) - KTX_MINUTES_FROM_SEOUL.get(arr, 0))
    base_minutes = max(distance, 18)
    conventional = dep in CONVENTIONAL_ONLY or arr in CONVENTIONAL_ONLY

    trains: list[Train] = []
    departs_at = datetime.combine(day, _FIRST_DEPARTURE, KST)
    last = datetime.combine(day, _LAST_DEPARTURE, KST)
    while departs_at <= last:
        if conventional:
            grade = rng.choice(("ITX-새마을", "ITX-마음", "무궁화호"))
            minutes = int(base_minutes * 1.7) + rng.randint(0, 12)
            number = rng.randint(1001, 1599)
            fare = 2600 + 210 * minutes
        else:
            grade = "KTX"
            minutes = base_minutes + rng.randint(0, 9)
            number = rng.randint(101, 399)
            fare = 2700 + 330 * minutes
        trains.append(
            Train(
                train_no=str(number),
                grade=grade,
                dep=dep,
                arr=arr,
                departs_at=departs_at,
                arrives_at=departs_at + timedelta(minutes=minutes),
                fare=fare - fare % 100,
                seats_available=rng.random() > 0.12,
            )
        )
        departs_at += timedelta(minutes=rng.choice(_HEADWAYS))
    return trains
