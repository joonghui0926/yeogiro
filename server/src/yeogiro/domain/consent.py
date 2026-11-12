from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

OPTION_TTL_SECONDS = 180
MAX_HOLDS_PER_DAY = 3
MAX_ACTIVE_HOLDS = 1
MIN_MINUTES_BEFORE_DEPARTURE = 20


class Verdict(StrEnum):
    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


@dataclass(frozen=True, slots=True)
class GateInput:
    option_is_latest: bool
    option_age_seconds: float | None
    proposal_heard: bool
    verdict: Verdict
    tester_registered: bool
    holds_today: int
    active_holds: int
    minutes_to_departure: float | None
    duplicate_hold: bool
    booking_enabled: bool


@dataclass(frozen=True, slots=True)
class GateCheck:
    code: str
    label: str
    passed: bool


@dataclass(frozen=True, slots=True)
class GateDecision:
    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_codes(self) -> tuple[str, ...]:
        return tuple(check.code for check in self.checks if not check.passed)


def evaluate(gate: GateInput) -> GateDecision:
    fresh = gate.option_age_seconds is not None and gate.option_age_seconds <= OPTION_TTL_SECONDS
    lead_ok = (
        gate.minutes_to_departure is not None
        and gate.minutes_to_departure >= MIN_MINUTES_BEFORE_DEPARTURE
    )
    within_limits = gate.holds_today < MAX_HOLDS_PER_DAY and gate.active_holds < MAX_ACTIVE_HOLDS
    return GateDecision(
        checks=(
            GateCheck("option", "이번 통화의 최근 제안, 3분 이내", gate.option_is_latest and fresh),
            GateCheck("heard", "제안을 끝까지 들음", gate.proposal_heard),
            GateCheck("consent", "명확한 동의", gate.verdict is Verdict.YES),
            GateCheck("tester", "등록된 테스터", gate.tester_registered),
            GateCheck("limits", "하루 3건, 동시 1건 이하", within_limits),
            GateCheck("lead", "출발 20분 전", lead_ok),
            GateCheck("duplicate", "같은 열차 중복 없음", not gate.duplicate_hold),
            GateCheck("switch", "예약 스위치 켜짐", gate.booking_enabled),
        )
    )
