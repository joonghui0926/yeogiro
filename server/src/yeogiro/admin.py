from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import time
from datetime import date, datetime, timedelta
from datetime import time as clock
from typing import Any

import httpx
from google.cloud import firestore

from yeogiro.adapters.openai.realtime import RealtimeClient, RealtimeError
from yeogiro.adapters.rail.korail_runs import KorailRuns
from yeogiro.adapters.rail.tago import TagoTimetable
from yeogiro.adapters.store.memory import DEMO_TESTER
from yeogiro.calls.voice_session import realtime_session
from yeogiro.config import KST, load_settings
from yeogiro.domain.routing import Journey
from yeogiro.ports import RailMode, RailUnavailable

PHONE_URL = "https://yeogiro-kaist.web.app"
ALIASES = (
    "김순자",
    "이영수",
    "박정희",
    "최명숙",
    "정만복",
    "강옥순",
    "조병철",
    "윤금자",
    "장덕수",
    "임춘자",
    "한상철",
    "오말순",
)


async def seed_testers(count: int, home: str) -> None:
    db = firestore.AsyncClient(project=load_settings().firebase_project)
    for number in range(1, count + 1):
        ref = db.collection("testers").document(f"t{number:02d}")
        snapshot = await ref.get()
        data = snapshot.to_dict() or {}
        if not data:
            data = {
                "label": f"테스터 {number}",
                "alias": ALIASES[(number - 1) % len(ALIASES)],
                "homeStation": home,
                "senior": None,
                "token": secrets.token_urlsafe(9),
            }
            await ref.set(data)
        print(f"{data['label']:<8} {data['alias']}  {PHONE_URL}/t/{data['token']}")


async def add_admin(email: str) -> None:
    db = firestore.AsyncClient(project=load_settings().firebase_project)
    await (
        db.collection("admins").document(email.lower()).set({"addedAt": firestore.SERVER_TIMESTAMP})
    )
    print(f"admin added: {email}")


async def set_flags(values: dict[str, Any]) -> None:
    db = firestore.AsyncClient(project=load_settings().firebase_project)
    await db.collection("config").document("runtime").set(values, merge=True)
    print(json.dumps(values, ensure_ascii=False))


async def check_voice() -> None:
    settings = load_settings()
    async with httpx.AsyncClient() as http:
        client = RealtimeClient(settings.openai_api_key, http)
        session = realtime_session(settings, DEMO_TESTER)
        try:
            result = await client.validate_session(session)
        except RealtimeError as error:
            raise SystemExit(f"session rejected: {error}") from error
    accepted = result.get("session", {})
    print(f"session ok: model={accepted.get('model')} voice={settings.voice}")


async def plan_routes(dep: str, arr: str, day: date | None, after: str, until: str, check: bool) -> None:
    settings = load_settings()
    if not settings.tago_service_key:
        raise SystemExit("TAGO_SERVICE_KEY is not set")
    today = datetime.now(KST).date()
    day = day or today + timedelta(days=1)
    start = datetime.combine(day, clock.fromisoformat(after), KST)
    end = datetime.combine(day, clock.fromisoformat(until), KST)
    async with httpx.AsyncClient() as http:
        began = time.monotonic()
        table = await KorailRuns(settings.tago_service_key, http).timetable(day, today)
        loaded = time.monotonic() - began
        began = time.monotonic()
        journeys = table.options(dep, arr, start, end)
        planned = time.monotonic() - began
        print(
            f"{dep} → {arr} · {day} {after}~{until} · 시간표 {len(table):,}구간"
            f" · 불러오기 {loaded:.1f}초 · 계산 {planned * 1000:.0f}ms · 경로 {len(journeys)}개"
        )
        tago = TagoTimetable(settings.tago_service_key, http) if check else None
        for journey in journeys:
            print(await _describe(journey, tago))


async def _describe(journey: Journey, tago: TagoTimetable | None) -> str:
    parts: list[str] = []
    fare = 0
    for index, leg in enumerate(journey.legs):
        if index:
            wait = int((leg.departs_at - journey.legs[index - 1].arrives_at).total_seconds() // 60)
            parts.append(f"({wait}분 환승)")
        grade = ""
        if tago:
            try:
                trains = await tago.search(leg.dep, leg.arr, leg.departs_at.date())
            except RailUnavailable:
                trains = []
            match = next((t for t in trains if t.train_no == leg.train_no), None)
            grade = f"{match.grade} " if match else "TAGO 미확인 "
            fare = fare + match.fare if match and fare >= 0 else -1
            await asyncio.sleep(0.4)
        parts.append(f"{leg.departs_at:%H:%M} {leg.dep} ─{grade}{leg.train_no}→ {leg.arrives_at:%H:%M} {leg.arr}")
    minutes = int(journey.duration.total_seconds() // 60)
    summary = f"{minutes // 60}시간 {minutes % 60}분 · 환승 {journey.transfers}회"
    if tago:
        summary += f" · {fare:,}원" if fare > 0 else " · 운임 미확인"
    return f"  {' '.join(parts)}  [{summary}]"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m yeogiro.admin")
    commands = parser.add_subparsers(dest="command", required=True)

    seed = commands.add_parser("seed-testers")
    seed.add_argument("count", type=int)
    seed.add_argument("--home", default="대전")

    admin = commands.add_parser("add-admin")
    admin.add_argument("email")

    flags = commands.add_parser("flags")
    flags.add_argument("--rail-mode", choices=[m.value for m in RailMode])
    flags.add_argument("--booking", choices=["on", "off"])
    flags.add_argument("--sold-out", choices=["on", "off"])
    flags.add_argument("--phone-band", choices=["on", "off"])

    commands.add_parser("check-voice")

    routes = commands.add_parser("routes", help="전체 시간표로 환승 경로 찾기")
    routes.add_argument("dep")
    routes.add_argument("arr")
    routes.add_argument("--day", type=date.fromisoformat)
    routes.add_argument("--after", default="06:00")
    routes.add_argument("--until", default="12:00")
    routes.add_argument("--check", action="store_true", help="TAGO로 열차 종류와 운임 확인")

    args = parser.parse_args()
    if args.command == "seed-testers":
        asyncio.run(seed_testers(args.count, args.home))
    elif args.command == "add-admin":
        asyncio.run(add_admin(args.email))
    elif args.command == "flags":
        values: dict[str, Any] = {}
        if args.rail_mode:
            values["railMode"] = args.rail_mode
        for name, key in (
            ("booking", "bookingEnabled"),
            ("sold_out", "forceSoldOut"),
            ("phone_band", "phoneBand"),
        ):
            if getattr(args, name):
                values[key] = getattr(args, name) == "on"
        asyncio.run(set_flags(values))
    elif args.command == "check-voice":
        asyncio.run(check_voice())
    elif args.command == "routes":
        asyncio.run(plan_routes(args.dep, args.arr, args.day, args.after, args.until, args.check))


if __name__ == "__main__":
    main()
