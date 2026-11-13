from __future__ import annotations

import asyncio
from bisect import bisect_left, bisect_right
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from yeogiro.domain.models import Itinerary, Train, TravelWindow
from yeogiro.ports import RailUnavailable


@dataclass(frozen=True, slots=True)
class TransferPolicy:
    min_minutes: int = 20
    max_minutes: int = 180
    max_queries: int = 600
    concurrency: int = 8
    timeout_seconds: float = 20

    def __post_init__(self) -> None:
        if not 0 < self.min_minutes <= self.max_minutes <= 1440:
            raise ValueError("invalid transfer waiting time")
        if min(self.max_queries, self.concurrency, self.timeout_seconds) <= 0:
            raise ValueError("transfer search limits must be positive")


@dataclass(frozen=True, slots=True)
class RouteSearch:
    routes: tuple[Itinerary, ...]
    source: str
    direct_found: bool
    complete: bool = True
    api_failed: bool = False


class TransferSearch:
    def __init__(
        self,
        search: Callable[[str, str, date], Awaitable[list[Train]]],
        stations: Callable[[], Awaitable[list[str]]],
        policy: TransferPolicy,
    ) -> None:
        self._search = search
        self._stations = stations
        self.policy = policy

    async def search(
        self,
        dep: str,
        arr: str,
        window: TravelWindow,
        earliest: datetime,
        direct_trains: list[Train] | None = None,
        direct_failed: bool = False,
    ) -> RouteSearch:
        policy = self.policy
        semaphore = asyncio.Semaphore(policy.concurrency)
        queries = 0
        api_failed = direct_failed
        complete = not direct_failed
        consecutive_errors = int(direct_failed)
        routes: dict[str, Itinerary] = {}
        direct_found = False

        async def query(start: str, end: str, day: date) -> list[Train]:
            nonlocal queries, complete, api_failed, consecutive_errors
            async with semaphore:
                if queries >= policy.max_queries or consecutive_errors >= 3:
                    complete = False
                    return []
                queries += 1
                try:
                    trains = await self._search(start, end, day)
                    consecutive_errors = 0
                    return trains
                except RailUnavailable:
                    consecutive_errors += 1
                    api_failed = True
                    complete = False
                    return []

        def valid_first(train: Train) -> bool:
            return (
                train.departs_at.date() == window.day
                and train.departs_at >= earliest
                and window.start <= train.departs_at.time() <= window.end
                and train.arrives_at > train.departs_at
                and train.seats_available is not False
            )

        async def via(station: str) -> None:
            firsts = [t for t in await query(dep, station, window.day) if valid_first(t)]
            # Each second leg is queried by its actual departure date, including midnight.
            days: set[date] = set()
            for first in firsts:
                low = first.arrives_at + timedelta(minutes=policy.min_minutes)
                high = first.arrives_at + timedelta(minutes=policy.max_minutes)
                day = low.date()
                while day <= high.date():
                    days.add(day)
                    day += timedelta(days=1)
            for day in sorted(days):
                seconds = sorted(await query(station, arr, day), key=lambda t: t.departs_at)
                starts = [t.departs_at for t in seconds]
                for first in firsts:
                    low = first.arrives_at + timedelta(minutes=policy.min_minutes)
                    high = first.arrives_at + timedelta(minutes=policy.max_minutes)
                    for second in seconds[bisect_left(starts, low) : bisect_right(starts, high)]:
                        wait = (second.departs_at - first.arrives_at).total_seconds() / 60
                        if (
                            policy.min_minutes <= wait <= policy.max_minutes
                            and second.arrives_at > second.departs_at
                            and second.seats_available is not False
                            and first.dep == dep
                            and first.arr == station
                            and second.dep == station
                            and second.arr == arr
                            and first.train_no != second.train_no
                        ):
                            route = Itinerary((first, second))
                            routes[route.key] = route

        try:
            async with asyncio.timeout(policy.timeout_seconds):
                direct = (
                    direct_trains
                    if direct_trains is not None
                    else await query(dep, arr, window.day)
                )
                direct_found = bool(direct)
                for train in direct:
                    if valid_first(train):
                        route = Itinerary((train,))
                        routes[route.key] = route
                stations = await self._stations()
                # A bounded worker pool avoids creating a task per station or a hub shortlist.
                candidates = iter(sorted(set(stations) - {dep, arr}))

                async def worker() -> None:
                    nonlocal complete
                    for station in candidates:
                        if queries >= policy.max_queries or consecutive_errors >= 3:
                            complete = False
                            return
                        await via(station)

                async with asyncio.TaskGroup() as group:
                    for _ in range(policy.concurrency):
                        group.create_task(worker())
        except TimeoutError:
            complete = False
        except RailUnavailable:
            complete = False
            api_failed = True
        ordered = sorted(
            routes.values(),
            key=lambda r: (len(r.legs), r.duration, r.legs[-1].arrives_at, r.key),
        )
        return RouteSearch(tuple(ordered), "tago", direct_found, complete, api_failed)
