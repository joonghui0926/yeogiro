from __future__ import annotations

import argparse
import asyncio
import json
import secrets
from typing import Any

import httpx
from google.cloud import firestore

from yeogiro.adapters.openai.realtime import RealtimeClient, RealtimeError
from yeogiro.adapters.store.memory import DEMO_TESTER
from yeogiro.calls.voice_session import realtime_session
from yeogiro.config import load_settings
from yeogiro.ports import RailMode

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


if __name__ == "__main__":
    main()
