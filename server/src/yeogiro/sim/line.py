from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, Self

from websockets.asyncio.client import ClientConnection, connect

from yeogiro.adapters.openai.realtime import SIDEBAND_URL


class TextLine:
    """A realtime socket in text mode that stands in for a phone call.

    Caller turns are typed instead of spoken, and the transcription events a real call would
    produce are synthesized so the session handles both the same way.
    """

    def __init__(self, api_key: str, session: dict[str, Any]) -> None:
        self._url = f"{SIDEBAND_URL}?model={session['model']}"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._session = {
            key: value
            for key, value in session.items()
            if key not in ("audio", "output_modalities")
        }
        self._session["output_modalities"] = ["text"]
        self._socket: ClientConnection | None = None
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._reader: asyncio.Task[None] | None = None
        self._turn = 0
        self.trace: list[str] = []
        self._opened = 0.0

    async def __aenter__(self) -> Self:
        self._socket = await connect(self._url, additional_headers=self._headers, max_size=None)
        await self.send({"type": "session.update", "session": self._session})
        self._reader = asyncio.create_task(self._read())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
        if self._socket is not None:
            await self._socket.close()
            self._socket = None
        self._events.put_nowait(None)

    async def send(self, event: dict[str, Any]) -> None:
        if self._socket is None:
            return
        if event.get("type") == "session.update" and "audio" in event.get("session", {}):
            return
        await self._socket.send(json.dumps(event, ensure_ascii=False))

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def speak(self, text: str) -> None:
        self._turn += 1
        item_id = f"caller_{self._turn}"
        for kind in ("input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped"):
            self._events.put_nowait({"type": kind})
        self._events.put_nowait({"type": "input_audio_buffer.committed", "item_id": item_id})
        await self.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
        self._events.put_nowait(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": item_id,
                "transcript": text,
            }
        )
        await self.send({"type": "response.create"})

    async def _read(self) -> None:
        assert self._socket is not None
        loop = asyncio.get_running_loop()
        self._opened = loop.time()
        async for raw in self._socket:
            event = json.loads(raw)
            kind = str(event.get("type", ""))
            if kind.startswith(("response.created", "response.done", "error")):
                status = event.get("response", {}).get("status", "") or event.get("error", {})
                self.trace.append(f"{loop.time() - self._opened:5.1f}s {kind} {status}")
            self._events.put_nowait(event)


class TextVoice:
    def __init__(self, api_key: str, session: dict[str, Any]) -> None:
        self.line = TextLine(api_key, session)

    def attach(self, call_id: str) -> TextLine:
        return self.line

    async def hangup(self, call_id: str) -> None:
        return None
