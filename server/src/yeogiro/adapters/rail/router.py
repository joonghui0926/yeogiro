from __future__ import annotations

import logging
from datetime import date, time

from yeogiro.adapters.rail.jobs import AssistRail, WorkerRail
from yeogiro.adapters.rail.mock import MockRail
from yeogiro.domain.models import Hold, Train
from yeogiro.ports import HoldRequest, RailMode, RailProvider, RailUnavailable

log = logging.getLogger(__name__)


class RailRouter:
    def __init__(
        self,
        timetable: RailProvider,
        mock: MockRail,
        worker: WorkerRail | None,
        assist: AssistRail | None,
    ) -> None:
        self._timetable = timetable
        self._mock = mock
        self._worker = worker
        self._assist = assist

    async def search(
        self, dep: str, arr: str, day: date, after: time | None, mode: RailMode, call_id: str
    ) -> tuple[list[Train], str]:
        if mode is RailMode.AUTO and self._worker is not None:
            try:
                trains = await self._worker.search(dep, arr, day, after, call_id)
                return await self._fill_fares(trains, dep, arr, day), self._worker.name
            except RailUnavailable as error:
                log.warning("korail search unavailable, falling back: %s", error)
        try:
            return await self._timetable.search(dep, arr, day), self._timetable.name
        except RailUnavailable as error:
            log.warning("timetable unavailable, using mock: %s", error)
            return await self._mock.search(dep, arr, day), self._mock.name

    async def hold(self, request: HoldRequest, mode: RailMode) -> Hold:
        if mode is RailMode.AUTO and self._worker is not None:
            try:
                return await self._worker.hold(request)
            except RailUnavailable as error:
                log.warning("korail hold unavailable, using mock: %s", error)
        if mode is RailMode.ASSIST and self._assist is not None:
            return await self._assist.hold(request)
        return await self._mock.hold(request)

    async def cancel(self, hold: Hold, call_id: str) -> None:
        if hold.provider == "korail" and self._worker is not None:
            await self._worker.cancel(hold, call_id)
        elif hold.provider == "assist" and self._assist is not None:
            await self._assist.cancel(hold, call_id)

    async def _fill_fares(self, trains: list[Train], dep: str, arr: str, day: date) -> list[Train]:
        if all(train.fare for train in trains):
            return trains
        try:
            reference = await self._timetable.search(dep, arr, day)
        except RailUnavailable:
            reference = await self._mock.search(dep, arr, day)
        fares = {train.train_no: train.fare for train in reference}
        return [
            train
            if train.fare
            else _with_fare(train, fares.get(train.train_no) or _estimate(train))
            for train in trains
        ]


def _with_fare(train: Train, fare: int) -> Train:
    return Train(
        train_no=train.train_no,
        grade=train.grade,
        dep=train.dep,
        arr=train.arr,
        departs_at=train.departs_at,
        arrives_at=train.arrives_at,
        fare=fare,
        seats_available=train.seats_available,
    )


def _estimate(train: Train) -> int:
    minutes = int(train.duration.total_seconds() // 60)
    per_minute = 330 if train.grade.startswith("KTX") else 210
    fare = 2700 + per_minute * minutes
    return fare - fare % 100
