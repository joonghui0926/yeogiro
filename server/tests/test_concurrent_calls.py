from typing import Any, cast

from yeogiro.adapters.messaging.inbox import InAppMessenger, mailbox_for
from yeogiro.adapters.store.memory import MemoryStore
from yeogiro.calls.registry import CallRegistry
from yeogiro.calls.session import CallDeps, CallSession
from yeogiro.ports import Flags
from yeogiro.ports import Tester as Caller

DEMO = Caller(id="t00", label="데모", alias="김여기", home_station="대전", senior=None)


class Recorder:
    def __getattr__(self, name: str) -> Any:
        async def method(*args: Any, **kwargs: Any) -> None:
            return None

        return method


def session(call_id: str, device: str | None) -> CallSession:
    deps = CallDeps(*(cast(Any, Recorder()) for _ in range(6)))
    return CallSession(call_id, f"rtc_{call_id}", DEMO, deps, Flags(), device)


def test_second_phone_on_shared_link_does_not_replace_first() -> None:
    registry = CallRegistry()
    first, second = session("a", "phone1aa"), session("b", "phone2bb")
    registry.add(first)
    registry.add(second)
    assert registry.live_on("t00", "phone1aa") is first
    assert registry.live_on("t00", "phone2bb") is second
    assert registry.live_on("t00", "phone3cc") is None


def test_payment_goes_to_the_call_that_requested_it() -> None:
    registry = CallRegistry()
    first, second = session("a", "phone1aa"), session("b", "phone2bb")
    second._payment_id = "pay_b"
    registry.add(first)
    registry.add(second)
    assert registry.awaiting("t00", "pay_b") is second
    assert registry.awaiting("t00", "pay_x") is None


async def test_each_phone_reads_only_its_own_messages() -> None:
    store = MemoryStore()
    messenger = InAppMessenger(store)
    await messenger.send("t00", "첫 번째 폰 표", "phone1aa")
    await messenger.send("t00", "두 번째 폰 표", "phone2bb")
    first = await store.inbox(mailbox_for("t00", "phone1aa"))
    second = await store.inbox(mailbox_for("t00", "phone2bb"))
    assert [m.body for m in first] == ["첫 번째 폰 표"]
    assert [m.body for m in second] == ["두 번째 폰 표"]
    assert mailbox_for("t00", None) == "t00"
