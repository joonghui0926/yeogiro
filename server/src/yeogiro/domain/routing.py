"""Journey planning over a full stop-level timetable.

Each train is broken into connections between consecutive stops and scanned in departure order
(Connection Scan). Round k only boards trains reachable with k-1 trains, so one scan per round gives
the earliest arrival for every transfer count, the same Pareto set RAPTOR produces.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_TRANSFER = timedelta(minutes=15)
MAX_LEGS = 3
MAX_SCANS = 60


@dataclass(frozen=True, slots=True)
class Connection:
    train_no: str
    dep: str
    arr: str
    departs_at: datetime
    arrives_at: datetime


@dataclass(frozen=True, slots=True)
class Leg:
    train_no: str
    dep: str
    arr: str
    departs_at: datetime
    arrives_at: datetime


@dataclass(frozen=True, slots=True)
class Journey:
    legs: tuple[Leg, ...]

    @property
    def departs_at(self) -> datetime:
        return self.legs[0].departs_at

    @property
    def arrives_at(self) -> datetime:
        return self.legs[-1].arrives_at

    @property
    def duration(self) -> timedelta:
        return self.arrives_at - self.departs_at

    @property
    def transfers(self) -> int:
        return len(self.legs) - 1

    def dominates(self, other: Journey) -> bool:
        return (
            self.departs_at >= other.departs_at
            and self.arrives_at <= other.arrives_at
            and self.transfers <= other.transfers
            and self != other
        )


Boarding = tuple[Connection, int]
Parent = tuple[Connection, Connection, int]


class Timetable:
    def __init__(self, connections: Iterable[Connection]) -> None:
        self._connections = sorted(connections, key=lambda c: (c.departs_at, c.arrives_at))
        self._starts = [c.departs_at for c in self._connections]

    def __len__(self) -> int:
        return len(self._connections)

    def earliest(
        self,
        origin: str,
        destination: str,
        depart_after: datetime,
        max_legs: int = MAX_LEGS,
        min_transfer: timedelta = MIN_TRANSFER,
    ) -> list[Journey]:
        """The earliest arrival for each number of trains, kept only when it beats fewer trains."""
        scan = self._connections[bisect_left(self._starts, depart_after) :]
        best: dict[str, tuple[datetime, int]] = {origin: (depart_after, 0)}
        parents: list[dict[str, Parent]] = [{}]
        journeys: list[Journey] = []

        for round_no in range(1, max_legs + 1):
            ready = dict(best)
            target = best.get(destination)
            boarded: dict[str, Boarding] = {}
            arrival: dict[str, datetime] = {}
            parent: dict[str, Parent] = {}
            for c in scan:
                if target is not None and c.departs_at >= target[0]:
                    break
                if c.train_no not in boarded:
                    reached = ready.get(c.dep)
                    if reached is None or c.dep == destination:
                        continue
                    at, from_round = reached
                    slack = min_transfer if from_round > 0 else timedelta(0)
                    if at + slack > c.departs_at:
                        continue
                    boarded[c.train_no] = (c, from_round)
                board, from_round = boarded[c.train_no]
                if c.arrives_at < arrival.get(c.arr, datetime.max.replace(tzinfo=c.arrives_at.tzinfo)):
                    arrival[c.arr] = c.arrives_at
                    parent[c.arr] = (board, c, from_round)
            parents.append(parent)
            for station, at in arrival.items():
                if station not in best or at < best[station][0]:
                    best[station] = (at, round_no)
            if destination in arrival and (target is None or arrival[destination] < target[0]):
                journeys.append(_rebuild(parents, destination, round_no))
        return journeys

    def options(
        self,
        origin: str,
        destination: str,
        start: datetime,
        end: datetime,
        max_legs: int = MAX_LEGS,
        min_transfer: timedelta = MIN_TRANSFER,
    ) -> list[Journey]:
        """Journeys leaving between start and end that no other journey beats."""
        found: dict[tuple[str, ...], Journey] = {}
        after = start
        for _ in range(MAX_SCANS):
            batch = [
                j
                for j in self.earliest(origin, destination, after, max_legs, min_transfer)
                if j.departs_at <= end
            ]
            if not batch:
                break
            for journey in batch:
                found[tuple(f"{leg.train_no}@{leg.departs_at:%H%M}" for leg in journey.legs)] = journey
            after = min(j.departs_at for j in batch) + timedelta(minutes=1)
        journeys = list(found.values())
        kept = [j for j in journeys if not any(other.dominates(j) for other in journeys)]
        return sorted(kept, key=lambda j: (j.departs_at, j.transfers))


def _rebuild(parents: list[dict[str, Parent]], destination: str, round_no: int) -> Journey:
    legs: list[Leg] = []
    station, current = destination, round_no
    while current > 0:
        board, alight, previous = parents[current][station]
        legs.append(Leg(board.train_no, board.dep, alight.arr, board.departs_at, alight.arrives_at))
        station, current = board.dep, previous
    return Journey(tuple(reversed(legs)))
