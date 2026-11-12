from __future__ import annotations

from typing import Any

from yeogiro.calls.prompt import build_instructions
from yeogiro.calls.tools import TOOLS
from yeogiro.config import Settings
from yeogiro.ports import Tester


def realtime_session(settings: Settings, tester: Tester) -> dict[str, Any]:
    return {
        "type": "realtime",
        "model": settings.voice_model,
        "instructions": build_instructions(tester),
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "noise_reduction": {"type": "far_field"},
                "transcription": {"model": settings.transcribe_model, "language": "ko"},
                "turn_detection": {
                    "type": "semantic_vad",
                    "eagerness": "low",
                    "create_response": True,
                    "interrupt_response": True,
                },
            },
            "output": {"voice": settings.voice, "speed": settings.voice_speed},
        },
        "tools": TOOLS,
        "tool_choice": "auto",
    }
