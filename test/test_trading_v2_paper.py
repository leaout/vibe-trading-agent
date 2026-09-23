# coding: utf-8
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from types import SimpleNamespace

from fastapi.testclient import TestClient

from trading_v2.api import create_app
from trading_v2.config import AppSettings
from trading_v2.agent.models import StrategySpec
from trading_v2.domain.enums import SignalSide, TradingMode
from trading_v2.domain.market import InstrumentId
from trading_v2.domain.signal import Signal
from trading_v2.events import InMemoryEventStream
from trading_v2.paper.repository import PaperRepository
from trading_v2.paper.service import PaperTradingService
from trading_v2.sessions.repository import SessionRepository  # registers FK target
from trading_v2.storage.database import Database


class PaperRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = Database("sqlite:///:memory:")
        self.repository = PaperRepository(self.database)
        self.database.create_schema()

    def tearDown(self) -> None:
        self.database.close()

    def test_buy_is_filled_once_and_updates_cash_and_position(self) -> None:
        account = self.repository.ensure_default()
        signal_id = str(uuid4())
        order = self.repository.execute(
            account.id, str(uuid4()), signal_id, "cn_equity:XSHG:600519",
            "buy", Decimal("10"), Decimal("0.05"),
        )
        duplicate = self.repository.execute(
            account.id, str(uuid4()), signal_id, "cn_equity:XSHG:600519",
            "buy", Decimal("10"), Decimal("0.05"),
        )
        capped = self.repository.execute(
            account.id, str(uuid4()), str(uuid4()), "cn_equity:XSHG:600519",
            "buy", Decimal("10"), Decimal("0.05"),
        )
        detail = self.repository.detail(account.id)

        self.assertEqual(order.status, "filled")
        self.assertEqual(order.quantity, Decimal("5000"))
        self.assertEqual(duplicate.id, order.id)
        self.assertEqual(capped.status, "rejected")
        self.assertEqual(len(detail.orders), 2)
        self.assertEqual(detail.positions[0].available_quantity, Decimal("0"))
        self.assertLess(detail.account.cash, Decimal("950000"))

    def test_a_share_position_cannot_be_sold_on_purchase_day(self) -> None:
        account = self.repository.ensure_default()
        self.repository.execute(
            account.id, str(uuid4()), str(uuid4()), "cn_equity:XSHG:600519",
            "buy", Decimal("10"), Decimal("0.05"),
        )
        sell = self.repository.execute(
            account.id, str(uuid4()), str(uuid4()), "cn_equity:XSHG:600519",
            "sell", Decimal("10.5"), Decimal("0.05"),
        )

        self.assertEqual(sell.status, "rejected")
        self.assertIn("当日买入不可卖", sell.rejection_reason)


class PaperApiTest(unittest.TestCase):
    def test_system_account_is_created_and_can_bind_session(self) -> None:
        settings = AppSettings(database_url="sqlite:///:memory:", auth_enabled=False, _env_file=None)
        with TestClient(create_app(settings=settings)) as client:
            accounts = client.get("/api/v2/paper/accounts")
            created = client.post("/api/v2/sessions", json={"message": "观察 600519"})
            session_id = created.json()["id"]
            enabled = client.post(
                f"/api/v2/paper/sessions/{session_id}/enable", json={},
            )
            session = client.get(f"/api/v2/sessions/{session_id}")
            detail = client.get(f"/api/v2/paper/sessions/{session_id}")

            self.assertEqual(accounts.status_code, 200)
            self.assertEqual(len(accounts.json()), 1)
            self.assertEqual(enabled.status_code, 200)
            self.assertEqual(session.json()["session"]["mode"], "paper")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["account"]["name"], "系统模拟账户")


class PaperSignalExecutionTest(unittest.IsolatedAsyncioTestCase):
    async def test_candidate_signal_executes_only_through_bound_paper_account(self) -> None:
        database = Database("sqlite:///:memory:")
        database.create_schema()
        repository = PaperRepository(database)
        account = repository.ensure_default()
        session_id = str(uuid4())
        repository.bind(session_id, account.id)
        sessions = SimpleNamespace(get_session=lambda _: None)

        async def get_session(_):
            return SimpleNamespace(mode=TradingMode.PAPER)

        sessions.get_session = get_session
        events = InMemoryEventStream()
        service = PaperTradingService(repository, sessions, events)
        strategy = StrategySpec.model_validate({
            "name": "测试策略", "thesis": "测试候选信号进入模拟账户",
            "instrument": "cn_equity:XSHG:600519", "timeframe": "5m",
            "entry_rules": [{"indicator": "close", "operator": "gt", "value": 9}],
            "risk": {"max_position_pct": 0.05, "max_daily_loss_pct": 0.02},
        })
        now = datetime.now(timezone.utc)
        signal = Signal(
            session_id=session_id, strategy_version=1,
            instrument=InstrumentId(asset_class="cn_equity", venue="XSHG", symbol="600519"),
            timeframe="5m", side=SignalSide.BUY, strength=1,
            reason="测试", bar_time=now, indicators={"close": 10},
            expires_at=now + timedelta(minutes=5),
        )
        try:
            order = await service.process_signal(session_id, strategy, signal)
            self.assertIsNotNone(order)
            self.assertEqual(order.status, "filled")
            self.assertEqual(repository.detail(account.id).positions[0].quantity, Decimal("5000"))
        finally:
            database.close()
            await events.close()


if __name__ == "__main__":
    unittest.main()
