from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from google.cloud import firestore_v1 as firestore

from yeogiro.adapters.messaging.inbox import InAppMessenger
from yeogiro.adapters.openai.consent_judge import OpenAIConsentJudge
from yeogiro.adapters.openai.realtime import RealtimeClient
from yeogiro.adapters.payment.mock_onetouch import MockOneTouch
from yeogiro.adapters.rail.itineraries import TransferPolicy
from yeogiro.adapters.rail.jobs import AssistRail, JobQueue, WorkerRail
from yeogiro.adapters.rail.korail_runs import KorailRuns
from yeogiro.adapters.rail.mock import MockRail
from yeogiro.adapters.rail.router import RailRouter
from yeogiro.adapters.rail.tago import TagoTimetable
from yeogiro.adapters.store.firestore import FirestoreStore
from yeogiro.adapters.store.memory import MemoryStore
from yeogiro.calls.registry import CallRegistry
from yeogiro.calls.session import CallDeps
from yeogiro.config import KST, Settings
from yeogiro.ports import RailProvider, Store


@dataclass(slots=True)
class Runtime:
    settings: Settings
    http: httpx.AsyncClient
    store: Store
    realtime: RealtimeClient
    payments: MockOneTouch
    deps: CallDeps
    registry: CallRegistry
    runs: KorailRuns | None = None

    async def warm(self) -> None:
        if self.runs is not None:
            await self.runs.warm(datetime.now(KST).date())

    async def close(self) -> None:
        await self.http.aclose()


def build_runtime(settings: Settings) -> Runtime:
    http = httpx.AsyncClient()
    store: Store
    queue: JobQueue | None = None
    if settings.store == "memory":
        store = MemoryStore()
    else:
        db = firestore.AsyncClient(project=settings.firebase_project)
        store = FirestoreStore(db)
        queue = JobQueue(db)

    mock = MockRail()
    timetable: RailProvider = (
        TagoTimetable(settings.tago_service_key, http) if settings.tago_service_key else mock
    )
    runs = (
        KorailRuns(
            settings.tago_service_key, http, timedelta(minutes=settings.transfer_min_minutes)
        )
        if settings.tago_service_key
        else None
    )
    rail = RailRouter(
        timetable=timetable,
        mock=mock,
        worker=(
            WorkerRail(queue, settings.rail_search_timeout, settings.rail_hold_timeout)
            if queue
            else None
        ),
        assist=AssistRail(queue, settings.assist_hold_timeout) if queue else None,
        transfer_policy=TransferPolicy(
            min_minutes=settings.transfer_min_minutes,
            max_minutes=settings.transfer_max_minutes,
            max_queries=settings.transfer_max_queries,
            timeout_seconds=settings.transfer_timeout_seconds,
        ),
        hubs=runs.hubs if runs else None,
        sample_on_failure=True,
    )

    realtime = RealtimeClient(settings.openai_api_key, http)
    payments = MockOneTouch(store)
    deps = CallDeps(
        voice=realtime,
        rail=rail,
        judge=OpenAIConsentJudge(settings.openai_api_key, settings.judge_model, http),
        payments=payments,
        messenger=InAppMessenger(store),
        store=store,
    )
    return Runtime(
        settings=settings,
        http=http,
        store=store,
        realtime=realtime,
        payments=payments,
        deps=deps,
        registry=CallRegistry(),
        runs=runs,
    )
