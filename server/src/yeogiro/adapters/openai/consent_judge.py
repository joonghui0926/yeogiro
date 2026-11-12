from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from yeogiro.adapters.openai.realtime import API_BASE
from yeogiro.domain.consent import Verdict

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
전화 상담원이 어르신에게 열차 하나를 제안하고 예약할지 물었다.
replies_after_proposal은 그 뒤 어르신이 한 말을 순서대로 적은 것이다.
가장 마지막 말을 기준으로, 이 열차를 지금 예약하는 데 분명히 동의했는지 판정한다.
앞에서 요금이나 시각을 물었고 상담원이 답한 뒤 마지막에 동의했다면 동의로 본다.

- yes: 뜻이 분명한 동의. 짧은 대답, 사투리, 존댓말이 아닌 말도 뜻이 분명하면 yes.
  예: "응", "어어 그려", "그래 그걸로 혀", "네네 해 주세요", "좋아요 잡아 줘요", "그라믄 그걸로 해 주이소"
- no: 거절, 조건 변경 요구(시간, 날짜, 역, 인원), 취소.
  예: "아니 됐어", "좀 더 일찍 없어?", "내일 걸로 해 줘"
- unclear: 되물음, 못 들었다는 말, 망설임, 혼잣말, 딴 이야기, 질문으로 끝나는 말, 말이 없음.
  예: "응?", "뭐라고?", "음… 글쎄", "응 근데 얼마라고?", "우리 아들이 거기 살아"

조금이라도 애매하면 unclear다. 돈이 나가는 결정이라 보수적으로 판정한다."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["yes", "no", "unclear"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


class OpenAIConsentJudge:
    def __init__(self, api_key: str, model: str, http: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._model = model
        self._http = http

    async def judge(self, proposal: str, replies: list[str]) -> tuple[Verdict, str]:
        if not replies:
            return Verdict.UNCLEAR, "제안 뒤 발화 없음"
        payload = {"proposal": proposal, "replies_after_proposal": replies}
        body = {
            "model": self._model,
            "input": [
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "consent",
                    "strict": True,
                    "schema": SCHEMA,
                }
            },
            "temperature": 0,
        }
        try:
            response = await self._http.post(
                f"{API_BASE}/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
                timeout=8,
            )
            response.raise_for_status()
            parsed = json.loads(_output_text(response.json()))
            return Verdict(parsed["verdict"]), str(parsed["reason"])
        except (httpx.HTTPError, ValueError, KeyError) as error:
            log.warning("consent judge failed: %s", error)
            return Verdict.UNCLEAR, "판정 실패"


def _output_text(body: dict[str, Any]) -> str:
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return str(content["text"])
    raise ValueError("no output_text in response")
