from __future__ import annotations

import secrets
from datetime import datetime

from yeogiro.config import KST
from yeogiro.ports import InboxMessage, Store

SENDER = "여기로"


def mailbox_for(tester_id: str, device: str | None) -> str:
    """Messages go to the phone that made the call, so testers sharing a link don't see each other's."""
    return f"{tester_id}~{device}" if device else tester_id


class InAppMessenger:
    """Delivers to the in-app Messages screen. A carrier SMS adapter can replace it later."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def send(self, tester_id: str, body: str, device: str | None = None) -> InboxMessage:
        message = InboxMessage(
            id=f"msg_{secrets.token_hex(6)}",
            sender=SENDER,
            body=body,
            sent_at=datetime.now(KST),
        )
        await self._store.add_inbox_message(mailbox_for(tester_id, device), message)
        return message
