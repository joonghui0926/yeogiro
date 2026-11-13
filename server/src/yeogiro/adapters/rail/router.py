from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime, time

from yeogiro.adapters.rail.itineraries import RouteSearch, TransferPolicy, TransferSearch
from yeogiro.adapters.rail.jobs import AssistRail, WorkerRail
from yeogiro.adapters.rail.mock import MockRail
from yeogiro.adapters.rail.tago import TagoTimetable
from yeogiro.domain import fares
from yeogiro.domain.models import Hold, Itinerary, Train, TravelWindow
from yeogiro.domain.selection import choose_train
from yeogiro.ports import HoldRequest, RailMode, RailProvider, RailUnavailable

log = logging.getLogger(__name__)


class RailRouter:
    def __init__(
        self,
        timetable: RailProvider,
        mock: MockRail,
        worker: WorkerRail | None,
        assist: AssistRail | None,
        transfer_policy: TransferPolicy | None = None,
    ) -> None:
        self._timetable = timetable
        self._mock = mock
        self._worker = worker
        self._assist = assist
        self._transfer = (
            TransferSearch(
                timetable.search, timetable.station_names, transfer_policy or TransferPolicy()
            )
            if isinstance(timetable, TagoTimetable)
            else None
        )

    async def search_routes(
        self,
        dep: str,
        arr: str,
        window: TravelWindow,
        earliest: datetime,
        mode: RailMode,
        call_id: str,
        include_transfers: bool = False,
        force_sold_out: bool = False,
    ) -> RouteSearch:
        try:
            trains, source = await self.search(dep, arr, window.day, window.start, mode, call_id)
        except RailUnavailable:
            if self._transfer:
                return await self._transfer.search(dep, arr, window, earliest, [], True)
            return RouteSearch((), self._timetable.name, False, False, True)
        choice = choose_train(trains, window, earliest, force_sold_out)
        suitable = (
            choice is not None and window.start <= choice.train.departs_at.time() <= window.end
        )
        if self._transfer and (include_transfers or not suitable):
            result = await self._transfer.search(dep, arr, window, earliest, trains)
            # Keep worker seat data and the existing direct recommendation policy.
            direct = [
                Itinerary((t,))
                for t in trains
                if t.departs_at >= earliest and t.duration.total_seconds() > 0
            ]
            transfers = [r for r in result.routes if len(r.legs) == 2]
            return replace(
                result, routes=tuple(direct + transfers), source=source, direct_found=bool(trains)
            )
        routes = tuple(Itinerary((t,)) for t in trains if t.duration.total_seconds() > 0)
        return RouteSearch(routes, source, bool(trains))

    async def search(
        self, dep: str, arr: str, day: date, after: time | None, mode: RailMode, call_id: str
    ) -> tuple[list[Train], str]:
        if mode is RailMode.AUTO and self._worker is not None:
            try:
                trains = await self._worker.search(dep, arr, day, after, call_id)
                return await self._fill_fares(trains, dep, arr, day), self._worker.name
            except RailUnavailable as error:
                log.warning("korail search unavailable, falling back: %s", error)
        return await self._timetable.search(dep, arr, day), self._timetable.name

    async def hold_route(self, request: HoldRequest, route: Itinerary, mode: RailMode) -> Hold:
        if len(route.legs) == 1:
            return await self.hold(request, mode)
        holds: list[Hold] = []
        try:
            for train in route.legs:
                leg = replace(
                    request,
                    train=train,
                    fare_total=fares.fare_total(train, request.party, request.senior),
                )
                holds.append(await self._mock.hold(leg))
        except BaseException:
            for held in holds:
                await self._mock.cancel(held)
            raise
        return Hold(
            pnr="/".join(h.pnr for h in holds),
            train=route.legs[0],
            fare_total=sum(h.fare_total for h in holds),
            seat=None,
            pay_by=min(h.pay_by for h in holds if h.pay_by is not None),
            provider="mock",
            itinerary=route,
            leg_holds=tuple(holds),
        )

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
        if hold.leg_holds:
            for leg in hold.leg_holds:
                await self.cancel(leg, call_id)
            return
        if hold.provider == "korail" and self._worker is not None:
            await self._worker.cancel(hold, call_id)
        elif hold.provider == "assist" and self._assist is not None:
            await self._assist.cancel(hold, call_id)
        elif hold.provider == "mock":
            await self._mock.cancel(hold)

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
