# coding: utf-8
"""Health, status and real-time system event endpoints."""

import asyncio
from datetime import datetime
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from trading_v2.agent.providers import ModelProvider, ModelProviderError
from trading_v2.api.dependencies import (
    get_event_stream,
    get_model_provider,
    get_runtime_state,
    get_settings,
    require_auth,
)
from trading_v2.auth.models import User
from trading_v2.config.settings import AppSettings
from trading_v2.domain.base import utc_now
from trading_v2.domain.enums import ConnectionState
from trading_v2.events import InMemoryEventStream
from trading_v2.runtime import RuntimeSnapshot, RuntimeStateStore

router = APIRouter(tags=["system"])


class LivenessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "alive"
    service: str
    version: str
    timestamp: datetime = Field(default_factory=utc_now)


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    ready: bool
    phase: str
    timestamp: datetime = Field(default_factory=utc_now)


class ModelStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    decision_enabled: bool
    provider: str
    model: str
    api_key_env: str
    minimum_confidence: float


class ModelTestResponse(BaseModel):
    connected: bool
    provider: str
    model: str
    message: str


@router.get("/health/live", response_model=LivenessResponse)
async def liveness(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> LivenessResponse:
    return LivenessResponse(
        service=settings.service_name,
        version=settings.service_version,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    runtime_state: Annotated[RuntimeStateStore, Depends(get_runtime_state)],
) -> ReadinessResponse:
    snapshot = await runtime_state.snapshot()
    return ReadinessResponse(
        status="ready" if snapshot.ready else "not_ready",
        ready=snapshot.ready,
        phase=snapshot.phase.value,
    )


@router.get("/status", response_model=RuntimeSnapshot)
async def status(
    runtime_state: Annotated[RuntimeStateStore, Depends(get_runtime_state)],
) -> RuntimeSnapshot:
    return await runtime_state.snapshot()


@router.get("/model/status", response_model=ModelStatusResponse)
async def model_status(
    settings: Annotated[AppSettings, Depends(get_settings)],
    provider: Annotated[ModelProvider, Depends(get_model_provider)],
    _: Annotated[User, Depends(require_auth)],
) -> ModelStatusResponse:
    return ModelStatusResponse(
        enabled=settings.model_enabled,
        configured=settings.model_enabled and provider.configured,
        decision_enabled=settings.decision_enabled,
        provider=settings.model_provider,
        model=settings.model_name,
        api_key_env=settings.model_api_key_env,
        minimum_confidence=settings.decision_min_confidence,
    )


@router.post("/model/test", response_model=ModelTestResponse)
async def test_model(
    provider: Annotated[ModelProvider, Depends(get_model_provider)],
    settings: Annotated[AppSettings, Depends(get_settings)],
    runtime_state: Annotated[RuntimeStateStore, Depends(get_runtime_state)],
    _: Annotated[User, Depends(require_auth)],
) -> ModelTestResponse:
    if not settings.model_enabled:
        raise HTTPException(status_code=400, detail="决策模型未启用")
    try:
        payload: dict[str, Any] = await provider.complete_json(
            "你是连接测试。只输出 JSON。",
            "返回 status=ok。",
            {
                "type": "object",
                "properties": {"status": {"type": "string", "enum": ["ok"]}},
                "required": ["status"],
                "additionalProperties": False,
            },
        )
        if payload.get("status") != "ok":
            raise ModelProviderError("模型连接成功，但响应未通过格式校验")
    except ModelProviderError as exc:
        await runtime_state.set_component(
            "model", ConnectionState.DEGRADED,
            provider=settings.model_provider, message=str(exc),
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await runtime_state.set_component(
        "model", ConnectionState.CONNECTED,
        provider=settings.model_provider, message=f"{settings.model_name} connection verified",
    )
    return ModelTestResponse(
        connected=True, provider=settings.model_provider, model=settings.model_name,
        message="模型连接与 JSON 输出校验通过",
    )


@router.get("/events")
async def events(
    request: Request,
    event_stream: Annotated[InMemoryEventStream, Depends(get_event_stream)],
    _: Annotated[User, Depends(require_auth)],
    replay: int = Query(default=20, ge=0, le=500),
) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        subscription = await event_stream.subscribe(replay=replay)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.topic}\n"
                    f"data: {event.model_dump_json()}\n\n"
                )
        finally:
            await subscription.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
