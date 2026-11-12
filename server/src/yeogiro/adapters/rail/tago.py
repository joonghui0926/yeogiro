from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any

import httpx

from yeogiro.config import KST, REPO_ROOT
from yeogiro.domain.models import Hold, Train
from yeogiro.ports import HoldRequest, RailUnavailable

log = logging.getLogger(__name__)

BASE = "https://apis.data.go.kr/1613000/TrainInfo"
STATION_CACHE = REPO_ROOT / "server" / ".cache" / "tago_stations.json"


class TagoTimetable:
    """Public timetable and adult fares (data.go.kr 15098552). No seat data, so seats read as open.

    The station directory (name -> node id) is large and stable, so it is fetched once and cached
    on disk; every call after that only hits the train-search operation.
    """

    name = "tago"

    def __init__(self, service_key: str, http: httpx.AsyncClient) -> None:
        self._key = service_key
        self._http = http
        self._stations: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def search(self, dep: str, arr: str, day: date) -> list[Train]:
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
        trains = [self._train(item, dep, arr) for item in items]
        trains.sort(key=lambda t: t.departs_at)
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
                self._stations = cached
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
            for stations in lists:
                for station in stations:
                    self._stations[str(station["nodename"])] = str(station["nodeid"])
            _save_cache(self._stations)
            return self._stations

    async def _items(self, operation: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        query = {"serviceKey": self._key, "_type": "json", "pageNo": 1, **params}
        try:
            response = await self._http.get(f"{BASE}/{operation}", params=query, timeout=8)
            response.raise_for_status()
            payload = response.json()["response"]
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise RailUnavailable(f"tago {operation} failed: {error}") from error
        header = payload.get("header", {})
        if header.get("resultCode") not in ("00", "0", None):
            raise RailUnavailable(f"tago {operation}: {header.get('resultMsg')}")
        items = payload.get("body", {}).get("items") or {}
        item = items.get("item", []) if isinstance(items, dict) else []
        return item if isinstance(item, list) else [item]

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
            seats_available=True,
        )


def _stamp(value: Any) -> datetime:
    return datetime.strptime(str(value), "%Y%m%d%H%M%S").replace(tzinfo=KST)


def _load_cache() -> dict[str, str]:
    try:
        data = json.loads(STATION_CACHE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data else {}
    except (OSError, ValueError):
        return {}


def _save_cache(stations: dict[str, str]) -> None:
    try:
        STATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        STATION_CACHE.write_text(json.dumps(stations, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        log.warning("could not write station cache: %s", error)
