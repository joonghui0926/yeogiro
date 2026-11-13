from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from yeogiro.adapters.messaging.inbox import InAppMessenger
from yeogiro.adapters.payment.mock_onetouch import MockOneTouch, PaymentRequest
from yeogiro.adapters.rail.codec import hold_to_dict, itinerary_to_dict, mask_pnr, train_to_dict
from yeogiro.adapters.rail.router import RailRouter
from yeogiro.calls import lines
from yeogiro.calls.prompt import greeting_instructions, progress_message
from yeogiro.config import KST
from yeogiro.domain import consent, fares, speech
from yeogiro.domain.models import Choice, Hold, Itinerary, Proposal
from yeogiro.domain.selection import adjacent_train, choose_train
from yeogiro.domain.stations import is_supported
from yeogiro.domain.when import BOOKING_LEAD, PartOfDay, RelativeDay, resolve_day, resolve_window
from yeogiro.ports import (
    BookingRecord,
    ConsentJudge,
    Flags,
    HoldFailed,
    HoldRequest,
    RailMode,
    RailUnavailable,
    Store,
    Tester,
    VoiceCalls,
    VoiceChannel,
)

log = logging.getLogger(__name__)

SILENCE_NUDGE_SECONDS = 7.0
SILENCE_HANGUP_SECONDS = 10.0
SECONDS_PER_SPOKEN_CHAR = 0.16
SPOKEN_SYLLABLES_PER_SECOND = 5.5
TAIL_OVERLAP_MS = 1500
QUICK_HOLD_SECONDS = 2.5
WAIT_FILLER_FIRST_SECONDS = 4.0
WAIT_FILLER_EVERY_SECONDS = 8.0
PAYMENT_REMINDERS = ((15.0, lines.PAY_REMINDER), (35.0, lines.PAY_REMINDER_LAST))
PAYMENT_GIVE_UP_SECONDS = 60.0
TRANSCRIPT_GRACE_SECONDS = 2.5
TRANSCRIPT_GIVE_UP_SECONDS = 6.0
SMS_DELAY_SECONDS = 2.0
SLOWER_SPEED = 0.8


class CallState(StrEnum):
    DIALING = "dialing"
    GREETING = "greeting"
    LISTENING = "listening"
    SEARCHING = "searching"
    PROPOSED = "proposed"
    HOLDING = "holding"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    CLOSING = "closing"
    ENDED = "ended"


_PROGRESS = (
    CallState.GREETING,
    CallState.LISTENING,
    CallState.SEARCHING,
    CallState.PROPOSED,
    CallState.HOLDING,
    CallState.PAYMENT_PENDING,
    CallState.PAID,
)


CLIENT_FIELDS = ("ua", "audio", "mic")


@dataclass(frozen=True, slots=True)
class CallDeps:
    voice: VoiceCalls
    rail: RailRouter
    judge: ConsentJudge
    payments: MockOneTouch
    messenger: InAppMessenger
    store: Store


@dataclass(frozen=True, slots=True)
class Secured:
    ok: bool
    say: str


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]
Judgement = tuple[consent.Verdict, str]


class CallSession:
    def __init__(
        self,
        call_id: str,
        voice_call_id: str,
        tester: Tester,
        deps: CallDeps,
        flags: Flags,
        device: str | None = None,
    ) -> None:
        self.call_id = call_id
        self.voice_call_id = voice_call_id
        self.tester = tester
        self.device = device
        self.outbound: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.state = CallState.DIALING

        self._deps = deps
        self._rail_mode: RailMode = flags.rail_mode
        self._channel: VoiceChannel | None = None
        self._channel_ready = asyncio.Event()
        self._media_ready = asyncio.Event()
        self._closed = asyncio.Event()
        self._started = time.monotonic()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._writes: set[asyncio.Task[Any]] = set()
        self._seq = 0
        self._furthest = CallState.DIALING

        self._send_lock = asyncio.Lock()
        self._idle = asyncio.Event()
        self._idle.set()
        self._user_speaking = False
        self._last_activity = time.monotonic()
        self._last_response_done = 0.0
        self._last_ai_text = ""
        self._nudged = False
        self._tools_running = 0
        self._retry_response = False
        self._awaiting_transcripts: dict[str, float] = {}
        self._committed_at: dict[str, float] = {}
        self._transcripts_settled = asyncio.Event()
        self._transcripts_settled.set()

        self._options: dict[str, Proposal] = {}
        self._current: Proposal | None = None
        self._proposal_say = ""
        self._proposal_short = ""
        self._expect_proposal = False
        self._proposal_response: str | None = None
        self._proposal_items: set[str] = set()
        self._proposal_started = 0.0
        self._proposal_completed = False
        self._proposal_cut_at_ms: int | None = None
        self._replies: list[str] = []
        self._judgement: tuple[tuple[str, ...], asyncio.Task[Judgement]] | None = None
        self._consent_misses = 0
        self._senior = tester.senior
        self._senior_asked = False
        self._pending_choice: tuple[Choice, int] | None = None

        self._hold: Hold | None = None
        self._booking: BookingRecord | None = None
        self._payment_id: str | None = None

        self._reasks = 0
        self._interruptions = 0
        self._gate_failures = 0
        self._outcome = "abandoned"
        self._rail_source = ""
        self._search_details: dict[str, Any] = {}

        self._tools: dict[str, ToolHandler] = {
            "find_trains": self._find_trains,
            "set_senior": self._set_senior,
            "request_booking": self._request_booking,
            "cancel_booking": self._cancel_booking,
            "speak_slower": self._speak_slower,
            "end_call": self._end_call,
        }

    @property
    def payment_id(self) -> str | None:
        return self._payment_id

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    @property
    def quiet(self) -> bool:
        """True when the assistant is neither speaking nor working, so the caller can talk."""
        return (
            self._idle.is_set()
            and self._tools_running == 0
            and self.state not in (CallState.SEARCHING, CallState.HOLDING)
        )

    async def run(self) -> None:
        try:
            async with self._deps.voice.attach(self.voice_call_id) as channel:
                self._channel = channel
                self._channel_ready.set()
                self._spawn(self._watch_silence())
                async for event in channel.events():
                    await self._on_event(event)
                    if self.closed:
                        break
        except Exception as error:
            if not self.closed:
                log.exception("voice channel failed for %s", self.call_id)
                self._log("error", where="voice", message=str(error))
        finally:
            await self.hangup("system")

    async def on_media_connected(self, client: dict[str, str] | None = None) -> None:
        if self._media_ready.is_set():
            return
        self._media_ready.set()
        report = {
            key: str(value)[:200] for key, value in (client or {}).items() if key in CLIENT_FIELDS
        }
        if report:
            self._log("client", **report)
        await asyncio.wait_for(self._channel_ready.wait(), timeout=10)
        self._enter(CallState.GREETING)
        await self._respond(instructions=greeting_instructions())

    async def approve_payment(self, payment_id: str) -> bool:
        if payment_id != self._payment_id:
            return False
        return await self._deps.payments.approve(payment_id)

    async def hangup(self, by: str) -> None:
        if self.closed:
            return
        self._closed.set()
        self._enter(CallState.ENDED)
        with contextlib.suppress(Exception):
            await self._deps.voice.hangup(self.voice_call_id)
        self._emit({"type": "call.ended", "by": by})
        if self._payment_id:
            await self._deps.payments.expire(self._payment_id)
        if self._booking is not None and self._booking.status != "paid":
            await self._release_hold("call_ended")
        await self._finalize(by)
        await asyncio.gather(*self._writes, return_exceptions=True)
        current = asyncio.current_task()
        for task in list(self._tasks):
            if task is not current:
                task.cancel()
        if self._channel is not None:
            with contextlib.suppress(Exception):
                await self._channel.close()

    async def _on_event(self, event: dict[str, Any]) -> None:
        kind = str(event.get("type", ""))
        now = time.monotonic()

        if kind == "input_audio_buffer.speech_started":
            self._user_speaking = True
            self._last_activity = now
            self._nudged = False
            if not self._idle.is_set():
                self._interruptions += 1
                self._log("interrupt")

        elif kind == "input_audio_buffer.speech_stopped":
            self._user_speaking = False
            self._last_activity = now

        elif kind == "input_audio_buffer.committed":
            item_id = str(event.get("item_id", ""))
            self._committed_at[item_id] = self._last_activity
            self._awaiting_transcripts[item_id] = now
            self._transcripts_settled.clear()

        elif kind == "conversation.item.input_audio_transcription.completed":
            item_id = str(event.get("item_id", ""))
            text = str(event.get("transcript") or "").strip()
            if text:
                self._log("user", text=text)
                if self._committed_at.get(item_id, now) >= self._proposal_started:
                    self._replies.append(text)
                    self._judge_ahead()
            self._settle_transcript(item_id)

        elif kind == "conversation.item.input_audio_transcription.failed":
            self._settle_transcript(str(event.get("item_id", "")))

        elif kind == "response.created":
            self._idle.clear()
            if self._expect_proposal:
                self._expect_proposal = False
                self._proposal_response = str(event.get("response", {}).get("id", ""))
                self._proposal_items.clear()
                self._proposal_started = now
                self._proposal_completed = False
                self._proposal_cut_at_ms = None
                self._replies = []
                self._judgement = None

        elif kind == "response.output_item.added":
            if event.get("response_id") == self._proposal_response:
                self._proposal_items.add(str(event.get("item", {}).get("id", "")))

        elif kind in (
            "response.output_audio_transcript.done",
            "response.audio_transcript.done",
            "response.output_text.done",
        ):
            text = str(event.get("transcript") or event.get("text") or "").strip()
            if text:
                self._last_ai_text = text
                self._log("ai", text=text)
                if self._is_reask(text):
                    self._reasks += 1

        elif kind == "conversation.item.truncated":
            if event.get("item_id") in self._proposal_items:
                self._proposal_cut_at_ms = int(event.get("audio_end_ms") or 0)

        elif kind == "response.done":
            response = event.get("response", {})
            self._last_response_done = now
            self._idle.set()
            status = response.get("status")
            if status in ("failed", "incomplete"):
                details = json.dumps(response.get("status_details"), ensure_ascii=False)
                self._log("error", where="response", message=f"{status} {details}")
            if response.get("id") == self._proposal_response:
                self._proposal_completed = status == "completed"
            if self._retry_response:
                self._retry_response = False
                self._spawn(self._respond())
            if self.state is CallState.GREETING:
                self._enter(CallState.LISTENING)
            for item in response.get("output", []):
                if item.get("type") == "function_call":
                    self._spawn(self._run_tool(item))

        elif kind == "error":
            error = event.get("error") or {}
            if error.get("code") == "conversation_already_has_active_response":
                self._retry_response = True
                return
            if "already shorter than" in str(error.get("message", "")):
                # The caller spoke after playback had already finished, so there was nothing to cut.
                self._log("playback_complete")
                return
            self._log("error", where="realtime", message=json.dumps(error, ensure_ascii=False))

    async def _run_tool(self, item: dict[str, Any]) -> None:
        name = str(item.get("name", ""))
        try:
            args = json.loads(item.get("arguments") or "{}")
        except ValueError:
            args = {}
        self._tools_running += 1
        started = time.monotonic()
        self._log("tool_call", name=name, args=args)
        try:
            handler = self._tools.get(name)
            result = await handler(args) if handler else {"error": f"unknown tool {name}"}
        except Exception as error:
            log.exception("tool %s failed", name)
            result = {"ok": False, "error": str(error), "say": lines.SOMETHING_WENT_WRONG}
        finally:
            self._tools_running -= 1
        elapsed = int((time.monotonic() - started) * 1000)
        self._log("tool_result", name=name, result=result, ms=elapsed)
        if result is None or self.closed:
            return
        output = {
            "type": "function_call_output",
            "call_id": item.get("call_id"),
            "output": json.dumps(result, ensure_ascii=False),
        }
        await self._respond(items=[output])

    async def _find_trains(self, args: dict[str, Any]) -> dict[str, Any]:
        shift = args.get("shift")
        if shift in ("earlier", "later") and self._current is not None:
            return await self._find_adjacent(shift)

        departure = args.get("departure") or self.tester.home_station
        arrival = args.get("arrival")
        if not departure or not is_supported(departure):
            return {"need": "departure", "say": lines.ASK_DEPARTURE}
        if not isinstance(arrival, str) or not is_supported(arrival) or arrival == departure:
            return {"need": "arrival", "say": lines.ASK_ARRIVAL}

        now = datetime.now(KST)
        day = resolve_day(
            _enum(RelativeDay, args.get("relative_day"), RelativeDay.UNSPECIFIED),
            args.get("weekday"),
            _int(args.get("month")),
            _int(args.get("day_of_month")),
            now.date(),
        )
        if day is None:
            return {"need": "date", "say": lines.ASK_DATE}
        part = _enum(PartOfDay, args.get("part_of_day"), PartOfDay.ANY)
        window = resolve_window(day, part, args.get("clock_time"), now)
        party = min(max(_int(args.get("party")) or 1, 1), 4)

        self._invalidate_proposal()
        self._enter(CallState.SEARCHING)
        flags = await self._deps.store.flags()
        result = await self._deps.rail.search_routes(
            departure,
            arrival,
            window,
            now + BOOKING_LEAD,
            self._rail_mode,
            self.call_id,
            include_transfers=args.get("include_transfers") is True
            or args.get("prefer_transfer") is True,
            force_sold_out=flags.force_sold_out,
        )
        self._rail_source = result.source
        routes = list(result.routes)
        route_direction = args.get("route_direction")
        if route_direction in ("earlier", "later"):
            anchor = datetime.fromisoformat(args["route_departure"])
            routes = [
                r
                for r in routes
                if (
                    r.legs[0].departs_at < anchor
                    if route_direction == "earlier"
                    else r.legs[0].departs_at > anchor
                )
            ]
            routes.sort(key=lambda r: abs((r.legs[0].departs_at - anchor).total_seconds()))
        self._search_details = {
            "direct_found": result.direct_found,
            "search_complete": result.complete,
            "api_failed": result.api_failed,
            "alternatives": [
                itinerary_to_dict(r)
                for r in (
                    [r for r in routes if len(r.legs) == 1][:5]
                    + [r for r in routes if len(r.legs) == 2][:5]
                )
            ],
        }
        trains = [r.legs[0] for r in routes if len(r.legs) == 1]
        choice = choose_train(trains, window, now + BOOKING_LEAD, flags.force_sold_out)
        suitable = (
            choice is not None and window.start <= choice.train.departs_at.time() <= window.end
        )
        transfers = [r for r in routes if len(r.legs) == 2]
        if transfers and (not suitable or args.get("prefer_transfer") is True):
            route = transfers[0]
            choice = Choice(route.legs[0], None, route)
            self._rail_source = "tago"
        if choice is None:
            self._enter(CallState.LISTENING)
            return {
                **self._search_details,
                "status": "api_error"
                if result.api_failed
                else "search_incomplete"
                if not result.complete
                else "no_route",
                "need": "other_day",
                "say": "열차 정보 조회에 오류가 있어 경로를 확인하지 못했어요. 잠시 후 다시 찾아볼까요?"
                if result.api_failed
                else "일부 구간만 조회해서 경로를 아직 확인하지 못했어요. 다시 찾아볼까요?"
                if not result.complete
                else "해당 조건에 맞는 직통 또는 한 번 환승하는 경로를 찾지 못했어요. 다른 시간으로 찾아볼까요?",
            }

        legs = choice.itinerary.legs if choice.itinerary else (choice.train,)
        needs_senior = self._senior is None and any(fares.senior_discount_applies(t) for t in legs)
        if needs_senior and not self._senior_asked:
            self._senior_asked = True
            self._pending_choice = (choice, party)
            self._enter(CallState.LISTENING)
            return {"need": "senior", "say": lines.ASK_SENIOR}
        return self._propose(choice, party)

    async def _find_adjacent(self, direction: Literal["earlier", "later"]) -> dict[str, Any]:
        current = self._current
        assert current is not None
        train = current.train
        if current.itinerary and len(current.itinerary.legs) == 2:
            return await self._find_trains(
                {
                    "departure": train.dep,
                    "arrival": current.itinerary.legs[-1].arr,
                    "relative_day": "date",
                    "month": train.departs_at.month,
                    "day_of_month": train.departs_at.day,
                    "include_transfers": True,
                    "prefer_transfer": True,
                    "clock_time": train.departs_at.strftime("%H:%M"),
                    "part_of_day": "any",
                    "party": current.party,
                    "route_direction": direction,
                    "route_departure": train.departs_at.isoformat(),
                }
            )
        now = datetime.now(KST)
        self._enter(CallState.SEARCHING)
        try:
            trains, self._rail_source = await self._deps.rail.search(
                train.dep, train.arr, train.departs_at.date(), None, self._rail_mode, self.call_id
            )
        except RailUnavailable:
            self._enter(CallState.PROPOSED)
            return {"status": "api_error", "say": "조회 오류로 다른 열차를 확인하지 못했어요."}
        nearby = adjacent_train(trains, train, direction, now + BOOKING_LEAD)
        if nearby is None:
            self._enter(CallState.PROPOSED)
            side = "앞" if direction == "earlier" else "뒤"
            return {"need": "keep_current", "say": lines.NO_ADJACENT.format(side=side)}
        return self._propose(Choice(train=nearby, sold_out_preferred=None), current.party)

    async def _set_senior(self, args: dict[str, Any]) -> dict[str, Any]:
        self._senior = bool(args.get("is_senior"))
        self._write(self._deps.store.set_tester_senior(self.tester.id, self._senior))
        if self._pending_choice is not None:
            choice, party = self._pending_choice
            self._pending_choice = None
            return self._propose(choice, party)
        if self._current is not None:
            return self._propose(
                Choice(self._current.train, None, self._current.itinerary), self._current.party
            )
        return {"say": lines.SENIOR_NOTED}

    def _invalidate_proposal(self) -> None:
        self._current = None
        self._pending_choice = None
        self._proposal_completed = False
        self._expect_proposal = False
        self._replies = []
        self._judgement = None

    def _propose(self, choice: Choice, party: int) -> dict[str, Any]:
        now = datetime.now(KST)
        senior = bool(self._senior)
        route = choice.itinerary or Itinerary((choice.train,))
        discounted = senior and any(fares.senior_discount_applies(t) for t in route.legs)
        proposal = Proposal(
            option_id=f"opt_{secrets.token_hex(3)}",
            train=choice.train,
            party=party,
            senior=senior,
            fare_total=sum(fares.fare_total(t, party, senior) for t in route.legs),
            sold_out_preferred=choice.sold_out_preferred,
            created_at=now,
            itinerary=route,
        )
        self._options[proposal.option_id] = proposal
        self._current = proposal
        self._proposal_say = speech.proposal_sentence(proposal, now.date(), discounted)
        if (
            len(route.legs) > 1
            and not self._search_details.get("direct_found")
            and not self._search_details.get("api_failed")
        ):
            self._proposal_say = (
                "직통 열차는 조회되지 않았지만 환승 경로가 있어요. " + self._proposal_say
            )
        self._proposal_short = (
            self._proposal_say if len(route.legs) > 1 else speech.reconfirm_sentence(proposal.train)
        )
        self._expect_proposal = True
        self._consent_misses = 0
        self._enter(CallState.PROPOSED)
        return {
            **self._search_details,
            "status": "transfer_found" if len(route.legs) > 1 else "direct_found",
            "option_id": proposal.option_id,
            "say": self._proposal_say,
            "say_short": self._proposal_short,
            "facts": speech.proposal_facts(proposal, now.date(), discounted),
            "train": {
                **train_to_dict(proposal.train),
                "fareTotal": proposal.fare_total if route.fare is not None else None,
                "soldOutPreferred": (
                    train_to_dict(choice.sold_out_preferred) if choice.sold_out_preferred else None
                ),
            },
            "source": self._rail_source,
            "itinerary": itinerary_to_dict(route),
        }

    async def _request_booking(self, args: dict[str, Any]) -> dict[str, Any]:
        option_id = str(args.get("option_id", ""))
        proposal = self._options.get(option_id)
        now = datetime.now(KST)

        self._settle_transcript("")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._transcripts_settled.wait(), TRANSCRIPT_GRACE_SECONDS)
        replies = tuple(self._replies)
        ahead = self._judgement
        judging = ahead[1] if ahead and ahead[0] == replies else self._spawn(self._judge(replies))
        flags, bookings = await asyncio.gather(
            self._deps.store.flags(), self._deps.store.bookings_for(self.tester.id)
        )
        verdict, reason = await judging
        real = [b for b in bookings if b.provider in ("korail", "assist")]

        decision = consent.evaluate(
            consent.GateInput(
                option_is_latest=proposal is not None and proposal is self._current,
                option_age_seconds=(now - proposal.created_at).total_seconds()
                if proposal
                else None,
                proposal_heard=self._proposal_heard(),
                verdict=verdict,
                tester_registered=True,
                holds_today=sum(
                    1 for b in real if b.created_at.astimezone(KST).date() == now.date()
                ),
                active_holds=sum(1 for b in real if b.status == "held"),
                minutes_to_departure=(
                    (proposal.train.departs_at - now).total_seconds() / 60 if proposal else None
                ),
                duplicate_hold=proposal is not None
                and any(b.train_key == proposal.train.key and b.status == "held" for b in real),
                booking_enabled=flags.booking_enabled,
            )
        )
        self._log(
            "gate",
            passed=decision.passed,
            verdict=verdict.value,
            reason=reason,
            replies=list(replies),
            checks=[
                {"code": c.code, "label": c.label, "passed": c.passed} for c in decision.checks
            ],
        )
        self._write(
            self._deps.store.update_call(
                self.call_id, {"lastGate": {"passed": decision.passed, "verdict": verdict.value}}
            )
        )
        if not decision.passed or proposal is None:
            self._gate_failures += 1
            return self._refusal(decision, proposal)

        self._enter(CallState.HOLDING)
        securing = self._spawn(self._secure(proposal))
        done, _ = await asyncio.wait({securing}, timeout=QUICK_HOLD_SECONDS)
        if securing in done:
            secured: Secured = securing.result()
            return {"ok": secured.ok, "say": secured.say}
        self._spawn(self._announce_when_secured(securing))
        return {"ok": True, "status": "waiting", "say": lines.HOLDING}

    def _refusal(self, decision: consent.GateDecision, proposal: Proposal | None) -> dict[str, Any]:
        failed = set(decision.failed_codes)
        if proposal is not None and failed <= {"consent", "heard"}:
            self._consent_misses += 1
            if self._consent_misses >= 2:
                self._outcome = "no_consent"
                self._spawn(self._send_train_info(proposal))
                return {"ok": False, "say": lines.NOT_CONFIRMED_TWICE}
            self._expect_proposal = True
            return {"ok": False, "reason": "not_confirmed", "say": self._proposal_short}

        code = next((c for c in decision.failed_codes if c in lines.REFUSALS), "option")
        if code == "switch" and proposal is not None:
            self._spawn(self._send_train_info(proposal))
        result: dict[str, Any] = {"ok": False, "reason": code, "say": lines.REFUSALS[code]}
        if code == "option":
            result["next"] = "같은 조건으로 find_trains를 다시 부른다"
        return result

    async def _secure(self, proposal: Proposal) -> Secured:
        if proposal.itinerary and proposal.itinerary.fare is None:
            self._enter(CallState.LISTENING)
            return Secured(
                False, "일부 구간의 운임을 확인하지 못해서 모의 예약을 진행할 수 없어요."
            )
        request = HoldRequest(
            call_id=self.call_id,
            tester_id=self.tester.id,
            train=proposal.train,
            party=proposal.party,
            senior=proposal.senior,
            fare_total=proposal.fare_total,
        )
        try:
            hold = await self._deps.rail.hold_route(
                request, proposal.itinerary or Itinerary((proposal.train,)), self._rail_mode
            )
        except HoldFailed as error:
            self._log("hold_failed", reason=error.reason)
            self._enter(CallState.LISTENING)
            return Secured(ok=False, say=lines.SEAT_GONE)
        except RailUnavailable as error:
            self._log("hold_failed", reason=str(error))
            self._enter(CallState.LISTENING)
            self._spawn(self._send_train_info(proposal))
            return Secured(ok=False, say=lines.RAIL_DOWN)

        self._hold = hold
        self._booking = BookingRecord(
            id=f"bk_{self.call_id}",
            call_id=self.call_id,
            tester_id=self.tester.id,
            train_key=hold.itinerary.key if hold.itinerary else hold.train.key,
            pnr=hold.pnr,
            provider=hold.provider,
            status="held",
            created_at=datetime.now(KST),
            extra={
                "train": train_to_dict(hold.train),
                "fareTotal": hold.fare_total,
                "seat": hold.seat,
                "itinerary": itinerary_to_dict(hold.itinerary) if hold.itinerary else None,
                "legHolds": [hold_to_dict(leg) for leg in hold.leg_holds],
            },
        )
        await self._deps.store.save_booking(self._booking)
        summary = {
            "provider": hold.provider,
            "pnr": mask_pnr(hold.pnr),
            "fareTotal": hold.fare_total,
            "seat": hold.seat,
            "train": train_to_dict(hold.train),
            "itinerary": itinerary_to_dict(hold.itinerary) if hold.itinerary else None,
            "legHolds": [{**hold_to_dict(leg), "pnr": mask_pnr(leg.pnr)} for leg in hold.leg_holds],
        }
        self._log("hold", **summary)
        self._write(self._deps.store.update_call(self.call_id, {"booking": summary}))

        train = hold.train
        payment = await self._deps.payments.request(
            call_id=self.call_id,
            tester_id=self.tester.id,
            payer=self.tester.alias,
            amount=hold.fare_total,
            item=(
                f"{train.dep}→{hold.itinerary.legs[-1].arr} 환승 1회 · 구간별 모의 예약"
                if hold.itinerary
                else f"{train.dep}→{train.arr} {train.grade} {train.departs_at:%H:%M}"
            ),
        )
        self._payment_id = payment.id
        self._enter(CallState.PAYMENT_PENDING)
        self._emit(
            {
                "type": "payment.requested",
                "payment": {
                    "id": payment.id,
                    "amount": payment.amount,
                    "merchant": payment.merchant,
                    "item": payment.item,
                    "payer": payment.payer,
                },
            }
        )
        self._log("payment", status="requested", amount=payment.amount)
        self._spawn(self._await_payment(hold, payment))
        return Secured(
            ok=True,
            say=(
                "두 구간의 모의 예약을 준비했어요. 실제 좌석을 확보한 것은 아니에요. "
                + lines.PAY_PROMPT
            )
            if hold.itinerary
            else lines.PAY_PROMPT,
        )

    async def _announce_when_secured(self, securing: asyncio.Task[Secured]) -> None:
        waited = 0.0
        next_filler = WAIT_FILLER_FIRST_SECONDS
        while not securing.done() and not self.closed:
            await asyncio.sleep(0.5)
            waited += 0.5
            if waited >= next_filler and not securing.done():
                await self._say(lines.HOLDING_STILL)
                next_filler += WAIT_FILLER_EVERY_SECONDS
        if not self.closed:
            await self._say(securing.result().say)

    async def _await_payment(self, hold: Hold, payment: PaymentRequest) -> None:
        waited = 0.0
        approved = False
        for at, reminder in PAYMENT_REMINDERS:
            approved = await self._deps.payments.wait(payment.id, at - waited)
            waited = at
            if approved or self.closed:
                break
            await self._say(reminder)
        if not approved and not self.closed:
            approved = await self._deps.payments.wait(payment.id, PAYMENT_GIVE_UP_SECONDS - waited)
        if self.closed:
            return
        if not approved:
            await self._deps.payments.expire(payment.id)
            self._emit({"type": "payment.expired", "paymentId": payment.id})
            self._log("payment", status="expired")
            self._outcome = "payment_timeout"
            await self._release_hold("payment_timeout")
            await self._say(lines.PAY_EXPIRED)
            self._spawn(self._end_after_speech())
            return

        self._enter(CallState.PAID)
        self._outcome = "booked"
        self._log("payment", status="approved", amount=payment.amount)
        if self._booking is not None:
            self._booking.status = "paid"
            await self._deps.store.save_booking(self._booking)
        await self._say(lines.PAID)
        await asyncio.sleep(SMS_DELAY_SECONDS)
        await self._deliver(
            speech.ticket_message(hold, self._current.party if self._current else 1)
        )

    async def _cancel_booking(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._hold is None or self._booking is None or self._booking.status == "cancelled":
            return {"ok": False, "say": lines.NOTHING_TO_CANCEL}
        if self._payment_id:
            await self._deps.payments.expire(self._payment_id)
        await self._release_hold("caller_request")
        self._outcome = "cancelled"
        self._enter(CallState.LISTENING)
        return {"ok": True, "say": lines.CANCELLED}

    async def _speak_slower(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._channel is not None:
            await self._channel.send(
                {
                    "type": "session.update",
                    "session": {"type": "realtime", "audio": {"output": {"speed": SLOWER_SPEED}}},
                }
            )
        self._log("voice", speed=SLOWER_SPEED)
        return {"ok": True, "say_short": self._proposal_short or None}

    async def _end_call(self, args: dict[str, Any]) -> None:
        if self._outcome == "abandoned" and self._current is not None:
            self._outcome = "declined"
        self._enter(CallState.CLOSING)
        self._spawn(self._say_goodbye_and_end())
        return None

    async def _say_goodbye_and_end(self) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._idle.wait(), timeout=12)
        if lines.GOODBYE not in self._last_ai_text:
            self._log("goodbye", added=True)
            await self._say(lines.GOODBYE)
        await self._end_after_speech()

    async def _release_hold(self, reason: str) -> None:
        if self._hold is None or self._booking is None or self._booking.status == "cancelled":
            return
        try:
            await self._deps.rail.cancel(self._hold, self.call_id)
        except Exception:
            log.exception("cancel failed for %s", self.call_id)
        self._booking.status = "cancelled"
        self._booking.extra["cancelReason"] = reason
        self._booking.extra["cancelledAt"] = datetime.now(KST)
        with contextlib.suppress(Exception):
            await self._deps.store.save_booking(self._booking)
        self._log("cancel", reason=reason, provider=self._hold.provider)

    async def _send_train_info(self, proposal: Proposal) -> None:
        if proposal.itinerary and len(proposal.itinerary.legs) > 1:
            await self._deliver(
                "[여기로] 환승 열차 안내\n"
                + speech.route_description(proposal.itinerary)
                + "\n예약되지 않았습니다. 좌석 재고는 미확인입니다."
            )
            return
        train = proposal.train
        body = "\n".join(
            [
                "[여기로] 열차 안내",
                f"{train.departs_at.month}월 {train.departs_at.day}일 {train.dep}→{train.arr}",
                f"{train.grade} {train.train_no} {train.departs_at:%H:%M} 출발 · "
                f"{train.arrives_at:%H:%M} 도착",
                f"{proposal.fare_total:,}원 · 예약되지 않았습니다.",
            ]
        )
        await asyncio.sleep(SMS_DELAY_SECONDS)
        await self._deliver(body)

    async def _deliver(self, body: str) -> None:
        message = await self._deps.messenger.send(self.tester.id, body, self.device)
        self._emit(
            {
                "type": "message.received",
                "message": {
                    "id": message.id,
                    "sender": message.sender,
                    "body": message.body,
                    "sentAt": message.sent_at.isoformat(),
                },
            }
        )
        self._log("message", body=message.body)

    async def _watch_silence(self) -> None:
        while not self.closed:
            await asyncio.sleep(0.5)
            if not self._media_ready.is_set() or self._user_speaking or not self.quiet:
                continue
            if self.state not in (CallState.LISTENING, CallState.PROPOSED, CallState.PAID):
                continue
            playback = len(self._last_ai_text) * SECONDS_PER_SPOKEN_CHAR
            quiet_for = time.monotonic() - max(
                self._last_activity, self._last_response_done + playback
            )
            if self.state is CallState.PAID and quiet_for > SILENCE_NUDGE_SECONDS:
                self._log("silence", action="hangup")
                await self._say(lines.GOODBYE)
                await self._end_after_speech()
                return
            if not self._nudged and quiet_for > SILENCE_NUDGE_SECONDS:
                self._nudged = True
                self._log("silence", action="nudge")
                proposed = self.state is CallState.PROPOSED and self._proposal_short
                if proposed:
                    self._expect_proposal = True
                await self._say(self._proposal_short if proposed else lines.NUDGE)
            elif self._nudged and quiet_for > SILENCE_HANGUP_SECONDS:
                self._log("silence", action="hangup")
                await self._say(lines.SILENT_GOODBYE)
                await self._end_after_speech()
                return

    async def _end_after_speech(self) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._idle.wait(), timeout=12)
        spoken = len(self._last_ai_text) * SECONDS_PER_SPOKEN_CHAR
        remaining = spoken - (time.monotonic() - self._last_response_done)
        await asyncio.sleep(min(max(remaining, 0.6), 8.0))
        await self.hangup("assistant")

    async def _say(self, say: str) -> None:
        item = {
            "type": "message",
            "role": "system",
            "content": [{"type": "input_text", "text": progress_message(say)}],
        }
        await self._respond(items=[item])

    async def _respond(
        self, items: list[dict[str, Any]] | None = None, instructions: str | None = None
    ) -> None:
        if self.closed or self._channel is None:
            return
        async with self._send_lock:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._idle.wait(), timeout=10)
            for item in items or []:
                await self._channel.send({"type": "conversation.item.create", "item": item})
            request: dict[str, Any] = {"type": "response.create"}
            if instructions:
                request["response"] = {"instructions": instructions}
            self._idle.clear()
            await self._channel.send(request)

    async def _judge(self, replies: tuple[str, ...]) -> Judgement:
        return await self._deps.judge.judge(self._proposal_say, list(replies))

    def _judge_ahead(self) -> None:
        if self.state is not CallState.PROPOSED:
            return
        replies = tuple(self._replies)
        self._judgement = (replies, self._spawn(self._judge(replies)))

    def _settle_transcript(self, item_id: str) -> None:
        self._awaiting_transcripts.pop(item_id, None)
        stale = time.monotonic() - TRANSCRIPT_GIVE_UP_SECONDS
        for pending, since in list(self._awaiting_transcripts.items()):
            if since < stale:
                self._awaiting_transcripts.pop(pending)
        if not self._awaiting_transcripts:
            self._transcripts_settled.set()

    def _proposal_heard(self) -> bool:
        if not self._proposal_completed:
            return False
        if self._proposal_cut_at_ms is None:
            return True
        syllables = len(self._proposal_say.replace(" ", ""))
        spoken_ms = syllables / SPOKEN_SYLLABLES_PER_SECOND * 1000
        return self._proposal_cut_at_ms >= spoken_ms - TAIL_OVERLAP_MS

    def _is_reask(self, text: str) -> bool:
        return (
            text.rstrip().endswith("?")
            and text != lines.GREETING
            and self.state in (CallState.LISTENING, CallState.SEARCHING)
        )

    def _enter(self, state: CallState) -> None:
        if state is self.state:
            return
        self.state = state
        if state in _PROGRESS and _PROGRESS.index(state) > _rank(self._furthest):
            self._furthest = state
        self._log("state", state=state.value)
        self._write(self._deps.store.update_call(self.call_id, {"state": state.value}))

    async def _finalize(self, ended_by: str) -> None:
        stopped_at = None if self._outcome in ("booked", "declined") else self._furthest.value
        with contextlib.suppress(Exception):
            await self._deps.store.update_call(
                self.call_id,
                {
                    "status": "ended",
                    "endedAt": datetime.now(KST),
                    "endedBy": ended_by,
                    "durationSec": round(time.monotonic() - self._started),
                    "outcome": self._outcome,
                    "stoppedAt": stopped_at,
                    "reasks": self._reasks,
                    "interruptions": self._interruptions,
                    "gateFailures": self._gate_failures,
                    "consentMisses": self._consent_misses,
                    "railSource": self._rail_source,
                },
            )

    def _emit(self, event: dict[str, Any]) -> None:
        self.outbound.put_nowait(event)

    def _log(self, kind: str, **data: Any) -> None:
        self._seq += 1
        record = {
            "t": int((time.monotonic() - self._started) * 1000),
            "kind": kind,
            "at": datetime.now(KST),
            **data,
        }
        log.debug("%s %s %s", self.call_id, kind, data)
        self._write(self._deps.store.append_event(self.call_id, self._seq, record))

    def _spawn[T](self, coroutine: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._settle)
        return task

    def _write(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coroutine)
        self._writes.add(task)
        task.add_done_callback(self._settle)

    def _settle(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        self._writes.discard(task)
        if not task.cancelled() and task.exception() is not None:
            log.error("task failed in %s", self.call_id, exc_info=task.exception())


def _rank(state: CallState) -> int:
    return _PROGRESS.index(state) if state in _PROGRESS else -1


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _enum[E: StrEnum](kind: type[E], value: Any, default: E) -> E:
    try:
        return kind(value)
    except ValueError:
        return default
