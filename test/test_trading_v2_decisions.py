# coding: utf-8
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from trading_v2.agent.models import StrategySpec
from trading_v2.agent.providers import ModelProviderError
from trading_v2.decisions.repository import DecisionRepository
from trading_v2.decisions.service import DecisionService
from trading_v2.domain.enums import DecisionAction, SignalSide
from trading_v2.domain.market import InstrumentId
from trading_v2.domain.signal import Signal
from trading_v2.events import InMemoryEventStream
from trading_v2.sessions.repository import SessionRepository  # registers FK target
from trading_v2.signals.repository import SignalRepository  # registers FK target
from trading_v2.storage.database import Database


class StubProvider:
    provider_name = "test"
    model_name = "decision-test"

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls = 0
        self.user_prompts = []

    async def complete_json(self, system_prompt, user_prompt, schema):
        self.calls += 1
        self.user_prompts.append(user_prompt)
        if self.error is not None:
            raise self.error
        return self.payload

    async def close(self) -> None:
        return None


def make_strategy() -> StrategySpec:
    return StrategySpec.model_validate({
        "name": "AI 复核测试", "thesis": "确定性信号交给模型复核",
        "instrument": "us_equity:XNAS:AAPL", "timeframe": "5m",
        "entry_rules": [{"indicator": "close", "operator": "gt", "value": 100}],
        "risk": {"max_position_pct": 0.05, "max_daily_loss_pct": 0.02},
    })


def make_signal() -> Signal:
    now = datetime.now(timezone.utc)
    return Signal(
        session_id=uuid4(), strategy_version=1,
        instrument=InstrumentId(asset_class="us_equity", venue="XNAS", symbol="AAPL"),
        timeframe="5m", side=SignalSide.BUY, strength=0.8,
        reason="价格突破", bar_time=now, indicators={"close": 101.5},
    )


class DecisionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite:///:memory:")
        self.repository = DecisionRepository(self.database)
        self.database.create_schema()
        self.events = InMemoryEventStream()

    async def asyncTearDown(self) -> None:
        await self.events.close()
        self.database.close()

    async def test_valid_decision_is_persisted_and_idempotent(self) -> None:
        provider = StubProvider({
            "action": "BUY", "confidence": 0.91, "rationale": "趋势和量能一致",
        })
        service = DecisionService(provider, self.repository, self.events)
        signal = make_signal()

        first = await service.decide(signal, make_strategy())
        second = await service.decide(signal, make_strategy())

        self.assertEqual(first.action, DecisionAction.BUY)
        self.assertEqual(second.id, first.id)
        self.assertEqual(provider.calls, 1)

    async def test_low_confidence_is_safely_downgraded_to_hold(self) -> None:
        provider = StubProvider({
            "action": "buy", "confidence": 0.4, "rationale": "信号较弱",
        })
        decision = await DecisionService(
            provider, self.repository, self.events, minimum_confidence=0.65,
        ).decide(make_signal(), make_strategy())

        self.assertEqual(decision.action, DecisionAction.HOLD)
        self.assertEqual(decision.status, "completed")
        self.assertIn("最低置信度", decision.rationale)

    async def test_provider_failure_is_persisted_as_fallback_hold(self) -> None:
        provider = StubProvider(error=ModelProviderError("timeout"))
        decision = await DecisionService(
            provider, self.repository, self.events,
        ).decide(make_signal(), make_strategy())

        self.assertEqual(decision.action, DecisionAction.HOLD)
        self.assertEqual(decision.status, "fallback")
        self.assertIn("安全回退", decision.rationale)

    async def test_recent_public_news_is_included_as_untrusted_context(self) -> None:
        provider = StubProvider({
            "action": "hold", "confidence": 0.7, "rationale": "等待消息确认",
        })
        service = DecisionService(provider, self.repository, self.events)
        await service.decide(make_signal(), make_strategy(), [{
            "title": "Apple product update", "summary": "Public report",
            "source": "test", "published_at": "2026-09-24T06:00:00Z",
            "category": "STORY",
        }])

        self.assertIn("recent_news", provider.user_prompts[0])
        self.assertIn("Apple product update", provider.user_prompts[0])


if __name__ == "__main__":
    unittest.main()
