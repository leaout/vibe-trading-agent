# coding: utf-8
"""Authenticated API for locally stored broker connection settings."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from trading_v2.adapters.eastmoney_web import (
    InvalidEastMoneySessionPath,
    test_eastmoney_web_connection,
)
from trading_v2.api.dependencies import get_broker_config, require_auth
from trading_v2.auth.models import User
from trading_v2.models.crypto import decrypt_secret
from trading_v2.models.broker_config import BrokerConfigRecord, BrokerConfigRepository

router = APIRouter(prefix="/broker", tags=["broker-configuration"])
logger = logging.getLogger(__name__)


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


class BrokerConnectionTestResponse(BaseModel):
    connected: bool
    provider: Literal["eastmoney"] = "eastmoney"
    account_hint: str
    session_reused: bool
    checked_at: datetime
    message: str


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


@router.post("/test-connection", response_model=BrokerConnectionTestResponse)
async def test_connection(
    repository: Annotated[BrokerConfigRepository, Depends(get_broker_config)],
    _: Annotated[User, Depends(require_auth)],
) -> BrokerConnectionTestResponse:
    record = await asyncio.to_thread(repository.get)
    if record is None or not record.account_no_encrypted or not record.password_encrypted:
        raise HTTPException(status_code=409, detail="请先保存东方财富资金账号和交易密码")

    try:
        account_no = decrypt_secret(record.account_no_encrypted)
        password = decrypt_secret(record.password_encrypted)
    except Exception as exc:
        logger.warning("Eastmoney credentials could not be decrypted (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="本地券商凭证无法解密，请检查加密密钥文件。",
        ) from None

    try:
        result = await asyncio.to_thread(
            test_eastmoney_web_connection,
            account_no,
            password,
            record.session_file,
        )
    except InvalidEastMoneySessionPath as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ImportError as exc:
        logger.warning("Eastmoney web adapter dependency is unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="东方财富网页登录组件未安装，请按 requirements-v2.txt 安装依赖后重启服务。",
        ) from None
    except Exception as exc:
        logger.warning("Eastmoney read-only connection check failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="东方财富网页登录或只读校验失败。请在官方客户端确认账号、密码与账户状态后重试；服务端未回传券商原始响应。",
        ) from None

    return BrokerConnectionTestResponse(
        connected=result.connected,
        account_hint=result.account_hint,
        session_reused=result.session_reused,
        checked_at=datetime.now(timezone.utc),
        message=result.message,
    )
