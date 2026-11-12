from __future__ import annotations

from yeogiro.calls.session import CallSession


class CallRegistry:
    """Live sessions are held in memory, so the call server runs as a single instance."""

    def __init__(self) -> None:
        self._sessions: dict[str, CallSession] = {}

    def add(self, session: CallSession) -> None:
        self._sessions[session.call_id] = session

    def get(self, call_id: str) -> CallSession | None:
        return self._sessions.get(call_id)

    def live_for(self, tester_id: str) -> CallSession | None:
        return next(
            (s for s in self._sessions.values() if s.tester.id == tester_id and not s.closed),
            None,
        )

    def discard(self, call_id: str) -> None:
        self._sessions.pop(call_id, None)

    def live(self) -> list[CallSession]:
        return [s for s in self._sessions.values() if not s.closed]
