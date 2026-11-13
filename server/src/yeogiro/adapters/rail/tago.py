from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from datetime import date, datetime
from typing import Any

import httpx

from yeogiro.config import KST, REPO_ROOT
from yeogiro.domain.models import Hold, Train
from yeogiro.ports import HoldRequest, RailUnavailable

log = logging.getLogger(__name__)

BASE = "https://apis.data.go.kr/1613000/TrainInfo"
STATION_CACHE = REPO_ROOT / "server" / ".cache" / "tago_stations.json"
# Names Korail and the voice flow use for stations TAGO spells differently.
ALIASES = {"여수엑스포": "여수EXPO", "S수서": "수서", "S동탄": "동탄"}


class TagoTimetable:
    """Public timetable and adult fares (data.go.kr 15098552), without seat inventory.

    The station directory (name -> node id) is large and stable, so it is fetched once and cached
    on disk; every call after that only hits the train-search operation.
    """

    name = "tago"

    def __init__(self, service_key: str, http: httpx.AsyncClient) -> None:
        self._key = service_key
        self._http = http
        self._stations: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[tuple[str, str, date], tuple[float, list[Train]]] = OrderedDict()
        self._requests = asyncio.Semaphore(8)

    async def station_names(self) -> list[str]:
        return list(await self._directory())

    async def search(self, dep: str, arr: str, day: date) -> list[Train]:
        cache_key = (dep, arr, day)
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 60:
            self._cache.move_to_end(cache_key)
            return list(cached[1])
        stations = await self._directory()
        if dep not in stations or arr not in stations:
            raise RailUnavailable(f"unknown station {dep} or {arr}")
        items = await self._items(
            "GetStrtpntAlocFndTrainInfo",
            {
                "depPlaceId": stations[dep],
                "arrPlaceId": stations[arr],
                "depPlandTime": day.strftime("%Y%m%d"),
                "numOfRows": 500,
            },
        )
        try:
            trains = [self._train(item, dep, arr) for item in items]
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise RailUnavailable("invalid TAGO timetable data") from error
        trains.sort(key=lambda t: t.departs_at)
        self._cache[cache_key] = (time.monotonic(), trains)
        self._cache.move_to_end(cache_key)
        while len(self._cache) > 2048:
            self._cache.popitem(last=False)
        return trains

    async def hold(self, request: HoldRequest) -> Hold:
        raise RailUnavailable("timetable source cannot hold seats")

    async def cancel(self, hold: Hold) -> None:
        return None

    async def _directory(self) -> dict[str, str]:
        async with self._lock:
            if self._stations:
                return self._stations
            cached = _load_cache()
            if cached:
                self._stations = _with_aliases(cached)
                return self._stations
            cities = await self._items("GetCtyCodeList", {"numOfRows": 100})
            lists = await asyncio.gather(
                *(
                    self._items(
                        "GetCtyAcctoTrainSttnList", {"cityCode": c["citycode"], "numOfRows": 500}
                    )
                    for c in cities
                )
            )
            directory: dict[str, str] = {}
            try:
                for stations in lists:
                    for station in stations:
                        directory[str(station["nodename"])] = str(station["nodeid"])
            except (TypeError, KeyError) as error:
                raise RailUnavailable("invalid TAGO station directory") from error
            if not directory:
                raise RailUnavailable("empty TAGO station directory")
            _save_cache(directory)
            self._stations = _with_aliases(directory)
            return self._stations

    async def _items(self, operation: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, 9):
            batch, total = await self._page(operation, {**params, "pageNo": page})
            items.extend(batch)
            if len(items) >= total:
                return items
            if not batch:
                break
        raise RailUnavailable("TAGO pagination incomplete")

    async def _page(
        self, operation: str, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], int]:
        query = {"serviceKey": self._key, "_type": "json", "pageNo": 1, **params}
        try:
            async with self._requests:
                response = await self._http.get(f"{BASE}/{operation}", params=query, timeout=8)
            response.raise_for_status()
            payload = response.json()["response"]
            header = payload.get("header", {})
            if str(header.get("resultCode")) not in ("00", "0"):
                raise RailUnavailable(f"tago {operation}: rejected response")
            body = payload["body"]
            items = body.get("items") or {}
            item = items.get("item", []) if isinstance(items, dict) else []
            batch = item if isinstance(item, list) else [item]
            total = int(body.get("totalCount", len(batch)))
            if not all(isinstance(row, dict) for row in batch):
                raise ValueError("invalid items")
            return batch, total
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as error:
            # HTTP exception messages contain the serviceKey query parameter.
            raise RailUnavailable(f"tago {operation} failed") from error

    @staticmethod
    def _train(item: dict[str, Any], dep: str, arr: str) -> Train:
        return Train(
            train_no=str(int(item["trainno"])),
            grade=str(item["traingradename"]),
            dep=dep,
            arr=arr,
            departs_at=_stamp(item["depplandtime"]),
            arrives_at=_stamp(item["arrplandtime"]),
            fare=int(float(item.get("adultcharge") or 0)),
            seats_available=None,
        )


def _stamp(value: Any) -> datetime:
    return datetime.strptime(str(value), "%Y%m%d%H%M%S").replace(tzinfo=KST)


def _with_aliases(directory: dict[str, str]) -> dict[str, str]:
    extra = {ours: directory[theirs] for ours, theirs in ALIASES.items() if theirs in directory}
    return {**directory, **extra}


def _load_cache() -> dict[str, str]:
    try:
        data = json.loads(STATION_CACHE.read_text(encoding="utf-8"))
        return (
            data
            if isinstance(data, dict)
            and data
            and all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in data.items())
            else {}
        )
    except (OSError, ValueError):
        return {}


def _save_cache(stations: dict[str, str]) -> None:
    try:
        STATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        STATION_CACHE.write_text(json.dumps(stations, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        log.warning("could not write station cache: %s", error)
