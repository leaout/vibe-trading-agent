# coding: utf-8
"""Read-only V2 bridge to the legacy Eastmoney web-session capability."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EastMoneyConnectionTest:
    connected: bool
    account_hint: str
    session_reused: bool
    message: str


class InvalidEastMoneySessionPath(ValueError):
    """Raised when the local session path escapes the private data directory."""


def _resolve_session_file(value: str) -> Path:
    data_root = (Path.cwd() / "data").resolve()
    requested = Path(value).expanduser()
    resolved = (requested if requested.is_absolute() else Path.cwd() / requested).resolve()
    try:
        resolved.relative_to(data_root)
    except ValueError as exc:
        raise InvalidEastMoneySessionPath("网页登录会话文件必须放在服务端 data 目录内") from exc
    if resolved.exists() and not resolved.is_file():
        raise InvalidEastMoneySessionPath("网页登录会话文件路径必须指向文件")
    return resolved


def test_eastmoney_web_connection(
    account_no: str,
    password: str,
    session_file: str,
) -> EastMoneyConnectionTest:
    """Log in through the legacy web gateway and verify read-only account access."""
    from curs.broker.eastmoney_trade_api import EastMoneyTradeAPI

    resolved_session_file = _resolve_session_file(session_file)
    key_file = Path(
        os.getenv("TRADING_V2_MODEL_SECRET_KEY_FILE", "data/model-secret.key")
    ).expanduser().resolve()
    api = EastMoneyTradeAPI(
        session_file=str(resolved_session_file),
        session_key_file=str(key_file),
    )
    try:
        login_result = api.login(account_no=account_no, password=password)
        balance = api.get_balance()
        if not isinstance(balance, dict) or "enable_balance" not in balance:
            raise RuntimeError("东方财富账户只读校验未返回有效资金状态")
        return EastMoneyConnectionTest(
            connected=True,
            account_hint=f"••••{account_no[-4:]}" if len(account_no) >= 4 else "••••",
            session_reused=bool(login_result.get("cached")),
            message="东方财富网页登录成功，只读账户校验通过；未发送委托。",
        )
    finally:
        # Keep the encrypted on-disk session for the next explicit connection check.
        api.session.close()
