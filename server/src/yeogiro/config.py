from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

KST = ZoneInfo("Asia/Seoul")
REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str
    voice_model: str
    voice: str
    voice_speed: float
    transcribe_model: str
    judge_model: str
    store: str
    firebase_project: str
    tago_service_key: str | None
    rail_search_timeout: float
    rail_hold_timeout: float
    assist_hold_timeout: float
    allowed_origins: tuple[str, ...]
    transfer_min_minutes: int = 20
    transfer_max_minutes: int = 180
    transfer_max_queries: int = 600
    transfer_timeout_seconds: float = 20


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    origins = os.environ.get(
        "ALLOWED_ORIGINS",
        "https://yeogiro-kaist.web.app,https://yeogiro-kaist.firebaseapp.com,"
        "http://localhost:5199,http://localhost:5174",
    )
    return Settings(
        openai_api_key=api_key,
        voice_model=os.environ.get("VOICE_MODEL", "gpt-realtime-2.1"),
        voice=os.environ.get("VOICE", "marin"),
        voice_speed=float(os.environ.get("VOICE_SPEED", "0.9")),
        transcribe_model=os.environ.get("TRANSCRIBE_MODEL", "gpt-4o-transcribe"),
        judge_model=os.environ.get("JUDGE_MODEL", "gpt-4.1-mini"),
        store=os.environ.get("STORE", "firestore"),
        firebase_project=os.environ.get("FIREBASE_PROJECT", "yeogiro-kaist"),
        tago_service_key=os.environ.get("TAGO_SERVICE_KEY") or None,
        rail_search_timeout=float(os.environ.get("RAIL_SEARCH_TIMEOUT", "4")),
        rail_hold_timeout=float(os.environ.get("RAIL_HOLD_TIMEOUT", "25")),
        assist_hold_timeout=float(os.environ.get("ASSIST_HOLD_TIMEOUT", "150")),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        transfer_min_minutes=int(os.environ.get("TRANSFER_MIN_MINUTES", "20")),
        transfer_max_minutes=int(os.environ.get("TRANSFER_MAX_MINUTES", "180")),
        transfer_max_queries=int(os.environ.get("TRANSFER_MAX_QUERIES", "600")),
        transfer_timeout_seconds=float(os.environ.get("TRANSFER_TIMEOUT_SECONDS", "20")),
    )
