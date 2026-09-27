# coding: utf-8
"""Authenticated API for locally stored broker connection settings."""

import asyncio
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from trading_v2.api.dependencies import get_broker_config, require_auth
from trading_v2.auth.models import User
from trading_v2.models.broker_config import BrokerConfigRecord, BrokerConfigRepository

router = APIRouter(prefix="/broker", tags=["broker-configuration"])


class BrokerConfigInput(BaseModel):
    provider: Literal["eastmoney"] = "eastmoney"
    account_no: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=2_000)
    session_file: str = Field(default="data/eastmoney_trader.session", min_length=1, max_length=500)


class BrokerConfigResponse(BaseModel):
    provider: Literal["eastmoney"] = "eastmoney"
    configured: bool
    account_hint: str
    account_configured: bool
    password_configured: bool
    session_file: str
    updated_at: datetime | None = None


def _response(record: BrokerConfigRecord | None) -> BrokerConfigResponse:
    if record is None:
        return BrokerConfigResponse(
            configured=False,
            account_hint="",
            account_configured=False,
            password_configured=False,
            session_file="data/eastmoney_trader.session",
        )
    account_configured = bool(record.account_no_encrypted)
    password_configured = bool(record.password_encrypted)
    return BrokerConfigResponse(
        configured=account_configured and password_configured,
        account_hint=record.account_hint,
        account_configured=account_configured,
        password_configured=password_configured,
        session_file=record.session_file,
        updated_at=record.updated_at,
    )


@router.get("/config", response_model=BrokerConfigResponse)
async def get_config(
    repository: Annotated[BrokerConfigRepository, Depends(get_broker_config)],
    _: Annotated[User, Depends(require_auth)],
) -> BrokerConfigResponse:
    return _response(await asyncio.to_thread(repository.get))


@router.put("/config", response_model=BrokerConfigResponse)
async def save_config(
    payload: BrokerConfigInput,
    repository: Annotated[BrokerConfigRepository, Depends(get_broker_config)],
    _: Annotated[User, Depends(require_auth)],
) -> BrokerConfigResponse:
    current = await asyncio.to_thread(repository.get)
    if current is None and (not payload.account_no.strip() or not payload.password):
        raise HTTPException(status_code=422, detail="首次保存请填写资金账号和交易密码")
    if current and not current.account_no_encrypted and not payload.account_no.strip():
        raise HTTPException(status_code=422, detail="请填写资金账号")
    if current and not current.password_encrypted and not payload.password:
        raise HTTPException(status_code=422, detail="请填写交易密码")
    record = await asyncio.to_thread(repository.save, payload.model_dump())
    return _response(record)
