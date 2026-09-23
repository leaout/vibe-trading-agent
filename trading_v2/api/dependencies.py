# coding: utf-8
"""Typed FastAPI dependencies backed by application state."""

from datetime import datetime, timezone

from fastapi import HTTPException, Request
from trading_v2.auth.models import User
from trading_v2.auth.service import AuthService

from trading_v2.config.settings import AppSettings
from trading_v2.events import InMemoryEventStream
from trading_v2.market.provider import MarketDataProvider
from trading_v2.paper.service import PaperTradingService
from trading_v2.runtime import RuntimeStateStore
from trading_v2.sessions.service import TradingSessionService
from trading_v2.signals.runtime import SignalRuntime

AUTH_COOKIE = "curs_v2_session"


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_event_stream(request: Request) -> InMemoryEventStream:
    return request.app.state.event_stream


def get_runtime_state(request: Request) -> RuntimeStateStore:
    return request.app.state.runtime_state


def get_market_data(request: Request) -> MarketDataProvider:
    return request.app.state.market_data


def get_session_service(request: Request) -> TradingSessionService:
    return request.app.state.session_service


def get_signal_runtime(request: Request) -> SignalRuntime:
    return request.app.state.signal_runtime


def get_paper_service(request: Request) -> PaperTradingService:
    return request.app.state.paper_service


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


async def require_auth(request: Request) -> User:
    if not request.app.state.settings.auth_enabled:
        return User(id="development", username="development", created_at=datetime.now(timezone.utc))
    user = request.app.state.auth_service.user_from_token(request.cookies.get(AUTH_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="需要登录")
    return user


def get_current_user(request: Request) -> User | None:
    return request.app.state.auth_service.user_from_token(request.cookies.get(AUTH_COOKIE))
