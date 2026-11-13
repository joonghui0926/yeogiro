from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from yeogiro.adapters.messaging.inbox import mailbox_for
from yeogiro.adapters.openai.realtime import RealtimeError
from yeogiro.calls.session import CallSession
from yeogiro.calls.voice_session import realtime_session
from yeogiro.config import KST, load_settings
from yeogiro.ports import Tester
from yeogiro.runtime import Runtime, build_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("yeogiro").setLevel(os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("yeogiro.api")

HEARTBEAT_SECONDS = 15
SESSION_LINGER_SECONDS = 60


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = build_runtime(load_settings())
    app.state.runtime = runtime
    yield
    for session in runtime.registry.live():
        await session.hangup("shutdown")
    await runtime.close()


app = FastAPI(title="여기로 call server", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(load_settings().allowed_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class CreateCall(BaseModel):
    token: str
    sdp: str
    device: str | None = None


DEVICE_ID = re.compile(r"[a-z0-9]{6,32}")


def _device(value: str | None) -> str | None:
    return value if value and DEVICE_ID.fullmatch(value) else None


class TokenBody(BaseModel):
    token: str


class ConnectedBody(TokenBody):
    client: dict[str, str] | None = None


def _runtime(request: Request) -> Runtime:
    runtime: Runtime = request.app.state.runtime
    return runtime


async def _tester(runtime: Runtime, token: str) -> Tester:
    tester = await runtime.store.tester_by_token(token)
    if tester is None:
        raise HTTPException(status_code=403, detail="unknown tester")
    return tester


def _session(runtime: Runtime, call_id: str, tester: Tester) -> CallSession:
    session = runtime.registry.get(call_id)
    if session is None or session.tester.id != tester.id:
        raise HTTPException(status_code=404, detail="no such call")
    return session


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me")
async def me(token: str, request: Request) -> dict[str, Any]:
    runtime = _runtime(request)
    tester = await _tester(runtime, token)
    flags = await runtime.store.flags()
    return {
        "id": tester.id,
        "label": tester.label,
        "alias": tester.alias,
        "phoneBand": flags.phone_band,
    }


@app.post("/api/calls")
async def create_call(body: CreateCall, request: Request) -> dict[str, Any]:
    runtime = _runtime(request)
    tester = await _tester(runtime, body.token)
    device = _device(body.device)
    live = runtime.registry.live_on(tester.id, device) if device else None
    if live is not None:
        await live.hangup("replaced")

    flags = await runtime.store.flags()
    session_config = realtime_session(runtime.settings, tester)
    try:
        openai_call_id, answer_sdp = await runtime.realtime.create_call(body.sdp, session_config)
    except RealtimeError as error:
        log.error("realtime call failed: %s", error)
        raise HTTPException(status_code=502, detail="voice service unavailable") from error

    call_id = f"{datetime.now(KST):%m%d-%H%M%S}-{secrets.token_hex(2)}"
    await runtime.store.create_call(
        call_id,
        {
            "testerId": tester.id,
            "testerLabel": tester.label,
            "deviceId": device,
            "startedAt": datetime.now(KST),
            "status": "live",
            "state": "dialing",
            "model": runtime.settings.voice_model,
            "voice": runtime.settings.voice,
            "railMode": flags.rail_mode.value,
            "phoneBand": flags.phone_band,
            "openaiCallId": openai_call_id,
        },
    )
    session = CallSession(call_id, openai_call_id, tester, runtime.deps, flags, device)
    runtime.registry.add(session)
    task = asyncio.create_task(session.run())
    task.add_done_callback(lambda _: _forget_later(runtime, call_id))
    return {"callId": call_id, "sdp": answer_sdp, "phoneBand": flags.phone_band}


@app.post("/api/calls/{call_id}/connected")
async def connected(call_id: str, body: ConnectedBody, request: Request) -> dict[str, bool]:
    runtime = _runtime(request)
    session = _session(runtime, call_id, await _tester(runtime, body.token))
    await session.on_media_connected(body.client)
    return {"ok": True}


@app.post("/api/calls/{call_id}/hangup")
async def hangup(call_id: str, body: TokenBody, request: Request) -> dict[str, bool]:
    runtime = _runtime(request)
    session = _session(runtime, call_id, await _tester(runtime, body.token))
    await session.hangup("caller")
    return {"ok": True}


@app.get("/api/calls/{call_id}/events")
async def events(call_id: str, token: str, request: Request) -> StreamingResponse:
    runtime = _runtime(request)
    session = _session(runtime, call_id, await _tester(runtime, token))

    async def stream() -> AsyncIterator[str]:
        yield ": connected\n\n"
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(session.outbound.get(), HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("type") == "call.ended":
                return

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/payments/{payment_id}/approve")
async def approve_payment(payment_id: str, body: TokenBody, request: Request) -> dict[str, bool]:
    runtime = _runtime(request)
    tester = await _tester(runtime, body.token)
    session = runtime.registry.awaiting(tester.id, payment_id)
    if session is None or not await session.approve_payment(payment_id):
        raise HTTPException(status_code=409, detail="payment is not pending")
    return {"ok": True}


@app.get("/api/inbox")
async def inbox(token: str, request: Request, device: str | None = None) -> dict[str, Any]:
    runtime = _runtime(request)
    tester = await _tester(runtime, token)
    messages = await runtime.store.inbox(mailbox_for(tester.id, _device(device)))
    return {
        "messages": [
            {"id": m.id, "sender": m.sender, "body": m.body, "sentAt": m.sent_at.isoformat()}
            for m in messages
        ]
    }


def _forget_later(runtime: Runtime, call_id: str) -> None:
    async def forget() -> None:
        await asyncio.sleep(SESSION_LINGER_SECONDS)
        runtime.registry.discard(call_id)

    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop().create_task(forget())
