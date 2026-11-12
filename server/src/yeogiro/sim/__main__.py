"""Play scenario cards against the real voice model in text mode and print each conversation.

python -m yeogiro.sim               all cards
python -m yeogiro.sim 3 5           cards 3 and 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from yeogiro.adapters.messaging.inbox import InAppMessenger
from yeogiro.adapters.openai.consent_judge import OpenAIConsentJudge
from yeogiro.adapters.payment.mock_onetouch import MockOneTouch
from yeogiro.adapters.rail.mock import MockRail
from yeogiro.adapters.rail.router import RailRouter
from yeogiro.adapters.store.memory import MemoryStore
from yeogiro.calls.session import CallDeps, CallSession, CallState
from yeogiro.calls.voice_session import realtime_session
from yeogiro.config import Settings, load_settings
from yeogiro.ports import Flags, RailMode, Tester
from yeogiro.sim.line import TextVoice

CARDS = Path(__file__).resolve().parents[3] / "scenarios" / "cards.json"
QUIET_HOLD_SECONDS = 1.2
TURN_TIMEOUT_SECONDS = 45.0


async def play(card: dict[str, Any], settings: Settings, http: httpx.AsyncClient) -> dict[str, Any]:
    profile = card.get("tester", {})
    tester = Tester(
        id="sim",
        label=card["name"],
        alias="김여기",
        home_station=profile.get("home"),
        senior=profile.get("senior"),
    )
    flags = Flags(rail_mode=RailMode.MOCK, force_sold_out=card.get("sold_out", False))
    store = MemoryStore(testers={"sim": tester}, flags=flags)
    voice = TextVoice(settings.openai_api_key, realtime_session(settings, tester))
    mock = MockRail()
    deps = CallDeps(
        voice=voice,
        rail=RailRouter(mock, mock, None, None),
        judge=OpenAIConsentJudge(settings.openai_api_key, settings.judge_model, http),
        payments=MockOneTouch(store),
        messenger=InAppMessenger(store),
        store=store,
    )
    session = CallSession(f"card-{card['id']}", "sim", tester, deps, flags)
    runner = asyncio.create_task(session.run())
    phone = asyncio.create_task(_phone(session, card))
    started = time.monotonic()

    await session.on_media_connected()
    for step in card["turns"]:
        await _until_quiet(session, card)
        if session.closed:
            break
        if isinstance(step, str):
            await voice.line.speak(step)
        else:
            await asyncio.sleep(float(step.get("wait", 0)))
        await asyncio.sleep(0.3)

    await _until_quiet(session, card)
    if not session.closed:
        await asyncio.sleep(3)
        await session.hangup("simulator")
    await asyncio.wait_for(runner, timeout=15)
    phone.cancel()

    call = store.calls.get(session.call_id, {})
    events = store.events.get(session.call_id, [])
    return {
        "card": card,
        "events": events,
        "outcome": call.get("outcome"),
        "reasks": call.get("reasks", 0),
        "gate_failures": call.get("gateFailures", 0),
        "seconds": round(time.monotonic() - started),
        "trace": voice.line.trace,
    }


async def _phone(session: CallSession, card: dict[str, Any]) -> None:
    while True:
        event = await session.outbound.get()
        if event["type"] == "payment.requested" and card.get("pay", True):
            await asyncio.sleep(float(card.get("pay_after", 3)))
            await session.approve_payment(event["payment"]["id"])


async def _until_quiet(session: CallSession, card: dict[str, Any]) -> None:
    deadline = time.monotonic() + TURN_TIMEOUT_SECONDS
    quiet_since: float | None = None
    while time.monotonic() < deadline and not session.closed:
        tapping = card.get("pay", True) and session.state is CallState.PAYMENT_PENDING
        if session.quiet and not tapping:
            quiet_since = quiet_since or time.monotonic()
            if time.monotonic() - quiet_since >= QUIET_HOLD_SECONDS:
                return
        else:
            quiet_since = None
        await asyncio.sleep(0.1)


def render(result: dict[str, Any]) -> tuple[str, bool]:
    card = result["card"]
    out = [f"\n━━ 카드 {card['id']} · {card['name']}", f"   {card.get('why', '')}"]
    for event in result["events"]:
        kind = event["kind"]
        stamp = f"{event['t'] / 1000:5.1f}s"
        if kind == "ai":
            out.append(f"{stamp}  AI      {event['text']}")
        elif kind == "user":
            out.append(f"{stamp}  어르신  {event['text']}")
        elif kind == "tool_call":
            args = {k: v for k, v in event["args"].items() if k != "heard"}
            out.append(f"{stamp}    ▸ {event['name']} {json.dumps(args, ensure_ascii=False)}")
        elif kind == "gate":
            verdict = "통과" if event["passed"] else "막힘"
            out.append(f"{stamp}    ▸ 게이트 {verdict} ({event['verdict']}) {event['reason'][:60]}")
        elif kind in ("hold", "payment", "cancel", "silence", "hold_failed", "voice"):
            detail = {
                k: v for k, v in event.items() if k not in ("t", "kind", "at", "seq", "train")
            }
            out.append(f"{stamp}    ▸ {kind} {json.dumps(detail, ensure_ascii=False, default=str)}")
        elif kind == "message":
            out.append(f"{stamp}    ▸ 문자 {event['body'].splitlines()[0]}")
        elif kind == "error":
            out.append(f"{stamp}    ! {event['message'][:160]}")

    expect = card.get("expect", {})
    checks = []
    if "outcome" in expect:
        checks.append(result["outcome"] == expect["outcome"])
    if "not_outcome" in expect:
        checks.append(result["outcome"] != expect["not_outcome"])
    if "max_reasks" in expect:
        checks.append(result["reasks"] <= expect["max_reasks"])
    passed = all(checks)
    if not passed or card.get("trace"):
        out.extend(f"         {line}" for line in result["trace"])
    out.append(
        f"   결과 {result['outcome']} · 되묻기 {result['reasks']} · 게이트 차단 "
        f"{result['gate_failures']} · {result['seconds']}초 → {'통과' if passed else '실패'}"
    )
    return "\n".join(out), passed


async def main(selected: list[str]) -> None:
    settings = load_settings()
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    if selected:
        cards = [card for card in cards if str(card["id"]) in selected]
    limit = asyncio.Semaphore(3)

    async with httpx.AsyncClient() as http:

        async def guarded(card: dict[str, Any]) -> dict[str, Any]:
            async with limit:
                return await play(card, settings, http)

        results = await asyncio.gather(*(guarded(card) for card in cards))

    passed = 0
    for result in results:
        text, ok = render(result)
        passed += ok
        print(text)
    print(f"\n{passed}/{len(results)} 카드 통과")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m yeogiro.sim")
    parser.add_argument("cards", nargs="*")
    asyncio.run(main(parser.parse_args().cards))
