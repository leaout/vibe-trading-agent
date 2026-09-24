# coding: utf-8
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading_v2.domain.enums import AssetClass
from trading_v2.domain.market import Bar, InstrumentId
from trading_v2.market.public import _aggregate_bars


class PublicMarketAggregationTest(unittest.TestCase):
    def setUp(self) -> None:
        instrument = InstrumentId(
            symbol="AAPL", venue="XNAS", asset_class=AssetClass.US_EQUITY,
        )
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.bars = [
            Bar(
                instrument=instrument,
                timeframe="1mo",
                open_time=start + timedelta(days=31 * index),
                close_time=start + timedelta(days=31 * (index + 1)),
                open=Decimal(str(100 + index)),
                high=Decimal(str(105 + index)),
                low=Decimal(str(95 + index)),
                close=Decimal(str(102 + index)),
                volume=Decimal("10"),
                turnover=Decimal("1000"),
                source="test",
            )
            for index in range(12)
        ]

    def test_yearly_aggregation(self) -> None:
        result = _aggregate_bars(self.bars, "1y", 10)

        self.assertEqual(1, len(result))
        self.assertEqual("1y", result[0].timeframe)
        self.assertEqual(Decimal("100"), result[0].open)
        self.assertEqual(Decimal("113"), result[0].close)
        self.assertEqual(Decimal("120"), result[0].volume)

    def test_all_keeps_available_history(self) -> None:
        result = _aggregate_bars(self.bars, "all", 8)

        self.assertEqual(8, len(result))
        self.assertTrue(all(bar.timeframe == "all" for bar in result))


if __name__ == "__main__":
    unittest.main()
