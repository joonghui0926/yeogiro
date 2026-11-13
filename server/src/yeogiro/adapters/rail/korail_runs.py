from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any

import httpx

from yeogiro.config import KST, REPO_ROOT
from yeogiro.domain.routing import Connection, Timetable
from yeogiro.ports import RailUnavailable

BASE = "https://openapis.korail.com/api/run/v2/travelerTrainRunInfo"
CACHE_DIR = REPO_ROOT / "server" / ".cache" / "korail_runs"
PAGE_SIZE = 1000
MAX_PAGES = 30


def sample_day(day: date, today: date) -> date:
    """Run info ends yesterday, so a later day borrows the latest past day with the same weekday."""
    yesterday = today - timedelta(days=1)
    if day <= yesterday:
        return day
    weeks = -(-(day - yesterday).days // 7)
    return day - timedelta(days=7 * weeks)


class KorailRuns:
    """Every passenger train's stops for a day (data.go.kr 15125762, Korail run info).

    Holiday timetables and one-off changes on the target day are not reflected, so callers should
    confirm the chosen trains against TAGO for that day before offering them.
    """

    def __init__(self, service_key: str, http: httpx.AsyncClient) -> None:
        self._key = service_key
        self._http = http
        self._rows: dict[date, list[dict[str, str]]] = {}
        self._lock = asyncio.Lock()

    async def timetable(self, day: date, today: date) -> Timetable:
        source = sample_day(day, today)
        rows = await self._stops(source)
        return Timetable(connections(rows, day - source))

    async def _stops(self, day: date) -> list[dict[str, str]]:
        async with self._lock:
            if day in self._rows:
                return self._rows[day]
            path = CACHE_DIR / f"{day:%Y%m%d}.json"
            if path.exists():
                rows: list[dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))
            else:
                rows = await self._fetch(day)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            self._rows[day] = rows
            return rows

    async def _fetch(self, day: date) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for page in range(1, MAX_PAGES + 1):
            items, total = await self._page(day, page)
            rows.extend(
                {
                    "train": str(int(item["trn_no"])),
                    "seq": str(item["trn_run_sn"]),
                    "station": str(item["stn_nm"]),
                    "arr": str(item.get("trn_arvl_dt") or ""),
                    "dep": str(item.get("trn_dptre_dt") or ""),
                }
                for item in items
            )
            if len(rows) >= total or not items:
                return rows
        raise RailUnavailable("korail run info pagination incomplete")

    async def _page(self, day: date, page: int) -> tuple[list[dict[str, Any]], int]:
        params: dict[str, str | int] = {
            "serviceKey": self._key,
            "returnType": "JSON",
            "pageNo": page,
            "numOfRows": PAGE_SIZE,
            "cond[run_ymd::GTE]": f"{day:%Y%m%d}",
            "cond[run_ymd::LTE]": f"{day:%Y%m%d}",
        }
        try:
            response = await self._http.get(BASE, params=params, timeout=30)
            response.raise_for_status()
            body = response.json()["response"]["body"]
            items = (body.get("items") or {}).get("item") or []
            return (items if isinstance(items, list) else [items]), int(body["totalCount"])
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            # httpx messages carry the request URL, which contains the service key.
            raise RailUnavailable("korail run info failed") from error


def connections(rows: list[dict[str, str]], shift: timedelta) -> list[Connection]:
    stops: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        stops[row["train"]].append(row)
    result: list[Connection] = []
    for train, route in stops.items():
        route.sort(key=lambda r: int(r["seq"]))
        for here, there in pairwise(route):
            if not here["dep"] or not there["arr"]:
                continue
            departs, arrives = _time(here["dep"]) + shift, _time(there["arr"]) + shift
            if arrives > departs:
                result.append(Connection(train, here["station"], there["station"], departs, arrives))
    return result


def _time(value: str) -> datetime:
    return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
