from __future__ import annotations

from typing import Any

from yeogiro.domain.stations import STATIONS
from yeogiro.domain.when import WEEKDAYS, PartOfDay, RelativeDay

FIND_TRAINS: dict[str, Any] = {
    "type": "function",
    "name": "find_trains",
    "description": "어르신이 말한 조건으로 열차를 찾아 하나를 제안한다. 결과의 say를 그대로 읽는다.",
    "parameters": {
        "type": "object",
        "properties": {
            "prefer_transfer": {
                "type": "boolean",
                "description": "사용자가 환승 경로를 선택하거나 환승편 제안을 원하면 true",
            },
            "include_transfers": {
                "type": "boolean",
                "description": "직통편이 있어도 환승 대안을 함께 찾을 때 true",
            },
            "arrival": {"type": "string", "enum": list(STATIONS), "description": "도착역"},
            "departure": {
                "type": "string",
                "enum": list(STATIONS),
                "description": "어르신이 출발역을 말했을 때만 넣는다",
            },
            "relative_day": {
                "type": "string",
                "enum": [d.value for d in RelativeDay],
                "description": "오늘·내일·모레·이번 주·다음 주(담주)·날짜 지정. 날짜(17일)면 date",
            },
            "weekday": {
                "type": "string",
                "enum": list(WEEKDAYS),
                "description": "요일을 말했을 때만. 화욜, 화요일 → tue",
            },
            "month": {"type": "integer", "minimum": 1, "maximum": 12},
            "day_of_month": {"type": "integer", "minimum": 1, "maximum": 31},
            "part_of_day": {
                "type": "string",
                "enum": [p.value for p in PartOfDay],
                "description": "새벽·아침/오전·점심·오후·저녁·밤. 말하지 않았으면 any",
            },
            "clock_time": {
                "type": "string",
                "description": "시각을 말했을 때만 HH:MM. '네 시쯤'이면 04:00, 오전·오후는 part_of_day로",
            },
            "party": {"type": "integer", "minimum": 1, "maximum": 4, "description": "인원, 기본 1"},
            "shift": {
                "type": "string",
                "enum": ["earlier", "later"],
                "description": "방금 제안한 기차의 바로 앞 차(earlier)나 다음 차(later)를 원할 때만",
            },
            "heard": {"type": "string", "description": "어르신이 말한 원래 표현"},
        },
        "required": ["arrival", "relative_day", "part_of_day"],
    },
}

SET_SENIOR: dict[str, Any] = {
    "type": "function",
    "name": "set_senior",
    "description": "만 65세 이상인지에 대한 답을 저장하고 제안을 다시 받는다.",
    "parameters": {
        "type": "object",
        "properties": {"is_senior": {"type": "boolean"}},
        "required": ["is_senior"],
    },
}

REQUEST_BOOKING: dict[str, Any] = {
    "type": "function",
    "name": "request_booking",
    "description": "제안한 열차를 예약한다. 어르신이 분명히 동의했을 때만 부른다.",
    "parameters": {
        "type": "object",
        "properties": {"option_id": {"type": "string"}},
        "required": ["option_id"],
    },
}

CANCEL_BOOKING: dict[str, Any] = {
    "type": "function",
    "name": "cancel_booking",
    "description": "이번 통화에서 잡은 예약을 취소한다.",
    "parameters": {"type": "object", "properties": {}},
}

END_CALL: dict[str, Any] = {
    "type": "function",
    "name": "end_call",
    "description": "끝인사를 한 뒤 통화를 끝낸다.",
    "parameters": {"type": "object", "properties": {}},
}

SPEAK_SLOWER: dict[str, Any] = {
    "type": "function",
    "name": "speak_slower",
    "description": "잘 안 들린다거나 천천히 말해 달라고 할 때 말 속도를 늦춘다.",
    "parameters": {"type": "object", "properties": {}},
}

TOOLS: list[dict[str, Any]] = [
    FIND_TRAINS,
    SET_SENIOR,
    REQUEST_BOOKING,
    CANCEL_BOOKING,
    SPEAK_SLOWER,
    END_CALL,
]
