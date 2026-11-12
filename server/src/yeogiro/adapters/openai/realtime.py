from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any

import httpx
from websockets.asyncio.client import ClientConnection, connect

API_BASE = "https://api.openai.com/v1"
SIDEBAND_URL = "wss://api.openai.com/v1/realtime"


class RealtimeError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"{status}: {body[:500]}")
        self.status = status
        self.body = body


class RealtimeClient:
    def __init__(self, api_key: str, http: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._http = http

    @property
    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def create_call(self, offer_sdp: str, session: dict[str, Any]) -> tuple[str, str]:
        response = await self._http.post(
            f"{API_BASE}/realtime/calls",
            headers=self._auth,
            files={
                "sdp": (None, offer_sdp, "application/sdp"),
                "session": (None, json.dumps(session, ensure_ascii=False), "application/json"),
            },
            timeout=20,
        )
        if response.status_code >= 400:
            raise RealtimeError(response.status_code, response.text)
        location = response.headers.get("location", "")
        call_id = location.rstrip("/").rsplit("/", 1)[-1]
        if not call_id:
            raise RealtimeError(response.status_code, "missing call id in Location header")
        return call_id, response.text

    async def hangup(self, call_id: str) -> None:
        response = await self._http.post(
            f"{API_BASE}/realtime/calls/{call_id}/hangup", headers=self._auth, timeout=10
        )
        if response.status_code >= 400 and response.status_code != 404:
            raise RealtimeError(response.status_code, response.text)

    async def validate_session(self, session: dict[str, Any]) -> dict[str, Any]:
        response = await self._http.post(
            f"{API_BASE}/realtime/client_secrets",
            headers=self._auth,
            json={"session": session},
            timeout=20,
        )
        if response.status_code >= 400:
            raise RealtimeError(response.status_code, response.text)
        body: dict[str, Any] = response.json()
        return body

    def attach(self, call_id: str) -> Sideband:
        return Sideband(f"{SIDEBAND_URL}?call_id={call_id}", self._auth)


class Sideband:
    def __init__(self, url: str, headers: dict[str, str]) -> None:
        self._url = url
        self._headers = headers
        self._connection: ClientConnection | None = None

    async def __aenter__(self) -> Sideband:
        self._connection = await connect(
            self._url, additional_headers=self._headers, max_size=None, ping_interval=20
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def send(self, event: dict[str, Any]) -> None:
        if self._connection is None:
            raise RuntimeError("sideband is not connected")
        await self._connection.send(json.dumps(event, ensure_ascii=False))

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        if self._connection is None:
            raise RuntimeError("sideband is not connected")
        async for raw in self._connection:
            event: dict[str, Any] = json.loads(raw)
            yield event
