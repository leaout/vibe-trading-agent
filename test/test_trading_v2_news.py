# coding: utf-8
import unittest

from fastapi.testclient import TestClient

from trading_v2.api import create_app
from trading_v2.config import AppSettings
from trading_v2.domain.market import InstrumentId
from trading_v2.news.models import NewsArticle
from trading_v2.news.public import PublicNewsProvider
from trading_v2.news.repository import NewsRepository
from trading_v2.news.service import NewsService
from trading_v2.storage.database import Database


class FixtureNewsProvider(PublicNewsProvider):
    def __init__(self) -> None:
        super().__init__(cache_seconds=60)
        self.calls = 0

    async def _get(self, url, params, referer=None):
        self.calls += 1
        if "eastmoney" in url:
            return {"data": {"list": [{
                "code": "cn-1", "title": "A股财经快讯", "summary": "摘要",
                "url": "http://finance.eastmoney.com/a.html", "showTime": "2026-09-24 14:30:00",
                "mediaName": "东方财富",
            }]}}
        if "yahoo" in url:
            return {"news": [{
                "uuid": "us-1", "title": "Apple update", "link": "https://finance.yahoo.com/a",
                "publisher": "Yahoo Finance", "providerPublishTime": 1790231400, "type": "STORY",
            }]}
        return {"data": {"catalogs": [{
            "catalogName": "Latest Binance News", "articles": [{
                "code": "crypto-1", "title": "BTC market update", "releaseDate": 1790231400000,
            }],
        }]}}


class PublicNewsProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_routes_and_normalizes_three_asset_classes(self) -> None:
        provider = FixtureNewsProvider()
        try:
            china = await provider.get_news(InstrumentId(asset_class="cn_equity", venue="XSHG", symbol="600519"))
            us = await provider.get_news(InstrumentId(asset_class="us_equity", venue="XNAS", symbol="AAPL"))
            crypto = await provider.get_news(InstrumentId(asset_class="crypto", venue="BINANCE", symbol="BTCUSDT"))

            self.assertEqual(china[0].source, "东方财富")
            self.assertTrue(china[0].url.startswith("https://"))
            self.assertEqual(us[0].instrument, "us_equity:XNAS:AAPL")
            self.assertIn("BTC", crypto[0].title)
        finally:
            await provider.close()

    async def test_short_cache_avoids_duplicate_upstream_requests(self) -> None:
        provider = FixtureNewsProvider()
        instrument = InstrumentId(asset_class="us_equity", venue="XNAS", symbol="AAPL")
        try:
            await provider.get_news(instrument)
            await provider.get_news(instrument)
            self.assertEqual(provider.calls, 1)
        finally:
            await provider.close()

    async def test_refresh_persists_once_and_builds_bounded_decision_context(self) -> None:
        database = Database("sqlite:///:memory:")
        database.create_schema()
        provider = FixtureNewsProvider()
        service = NewsService(provider, NewsRepository(database))
        instrument = InstrumentId(asset_class="us_equity", venue="XNAS", symbol="AAPL")
        try:
            stored, first_created = await service.refresh(instrument)
            _, second_created = await service.refresh(instrument)
            other_instrument = InstrumentId(asset_class="us_equity", venue="XNAS", symbol="MSFT")
            other_stored, other_created = await service.refresh(other_instrument)
            context = await service.decision_context(instrument)

            self.assertEqual(len(stored), 1)
            self.assertEqual(len(first_created), 1)
            self.assertEqual(second_created, [])
            self.assertEqual(len(other_stored), 1)
            self.assertEqual(len(other_created), 1)
            self.assertEqual(context[0]["source"], "Yahoo Finance")
            self.assertNotIn("url", context[0])
        finally:
            await service.close()
            database.close()


class StubApiNews:
    def __init__(self) -> None:
        self.closed = False

    async def get_news(self, instrument, limit=20):
        return [NewsArticle(
            id="stub:1", title=f"{instrument.symbol} headline", url="https://example.com/news",
            source="stub", published_at="2026-09-24T06:00:00Z",
            asset_class=instrument.asset_class, instrument=instrument.canonical,
        )][:limit]

    async def close(self) -> None:
        self.closed = True


class NewsApiTest(unittest.TestCase):
    def test_news_endpoint_is_normalized_and_closes_provider(self) -> None:
        provider = StubApiNews()
        settings = AppSettings(database_url="sqlite:///:memory:", auth_enabled=False, _env_file=None)
        with TestClient(create_app(settings=settings, news_provider=provider)) as client:
            response = client.get(
                "/api/v2/news",
                params={"instrument": "us_equity:XNAS:AAPL", "limit": 10},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[0]["instrument"], "us_equity:XNAS:AAPL")
        self.assertTrue(provider.closed)


if __name__ == "__main__":
    unittest.main()
