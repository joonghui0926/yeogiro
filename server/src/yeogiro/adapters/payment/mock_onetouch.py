from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime

from yeogiro.config import KST
from yeogiro.ports import Store

MERCHANT = "여기로 기차예약"


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    id: str
    call_id: str
    tester_id: str
    amount: int
    merchant: str
    item: str
    payer: str
    requested_at: datetime


class MockOneTouch:
    """One-touch approval with no money movement. The phone shows the sheet and posts approval."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def request(
        self, call_id: str, tester_id: str, payer: str, amount: int, item: str
    ) -> PaymentRequest:
        payment = PaymentRequest(
            id=f"pay_{secrets.token_hex(6)}",
            call_id=call_id,
            tester_id=tester_id,
            amount=amount,
            merchant=MERCHANT,
            item=item,
            payer=payer,
            requested_at=datetime.now(KST),
        )
        self._pending[payment.id] = asyncio.get_running_loop().create_future()
        await self._store.save_payment(
            payment.id,
            {
                "callId": call_id,
                "testerId": tester_id,
                "amount": amount,
                "merchant": payment.merchant,
                "item": item,
                "status": "requested",
                "requestedAt": payment.requested_at,
            },
        )
        return payment

    async def wait(self, payment_id: str, timeout: float) -> bool:
        future = self._pending.get(payment_id)
        if future is None:
            return False
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout)
        except TimeoutError:
            return False

    async def approve(self, payment_id: str) -> bool:
        future = self._pending.get(payment_id)
        if future is None or future.done():
            return False
        future.set_result(True)
        await self._store.save_payment(
            payment_id, {"status": "approved", "approvedAt": datetime.now(KST)}
        )
        return True

    async def expire(self, payment_id: str) -> None:
        future = self._pending.pop(payment_id, None)
        if future is not None and not future.done():
            future.set_result(False)
            await self._store.save_payment(
                payment_id, {"status": "expired", "expiredAt": datetime.now(KST)}
            )

    def forget(self, payment_id: str) -> None:
        self._pending.pop(payment_id, None)
