# coding: utf-8
"""Keyless public financial-news routing for paper-trading research."""

import asyncio
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import aiohttp

from trading_v2.domain.enums import AssetClass
from trading_v2.domain.market import InstrumentId
from trading_v2.news.models import NewsArticle


class PublicNewsError(RuntimeError):
    """A public news source could not be queried or parsed."""


class PublicNewsProvider:
    def __init__(self, timeout_seconds: float = 8, cache_seconds: int = 60) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_seconds = cache_seconds
        self._session: aiohttp.ClientSession | None = None
        self._cache: dict[str, tuple[float, list[NewsArticle]]] = {}

    async def get_news(self, instrument: InstrumentId, limit: int = 20) -> list[NewsArticle]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        key = f"{instrument.canonical}:{limit}"
        cached = self._cache.get(key)
        if cached and monotonic() - cached[0] < self.cache_seconds:
            return cached[1]
        if instrument.asset_class == AssetClass.CN_EQUITY:
            articles = await self._eastmoney(instrument, limit)
        elif instrument.asset_class == AssetClass.US_EQUITY:
            articles = await self._yahoo(instrument, limit)
        elif instrument.asset_class == AssetClass.CRYPTO:
            articles = await self._binance(instrument, limit)
        else:
            raise ValueError(f"no public news provider for {instrument.asset_class.value}")
        articles = _deduplicate(articles)[:limit]
        self._cache[key] = (monotonic(), articles)
        return articles

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _get(self, url: str, params: dict[str, Any], referer: str | None = None) -> Any:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            )
        headers = {"User-Agent": "Mozilla/5.0 VibeTradingAgent/0.1"}
        if referer:
            headers["Referer"] = referer
        try:
            async with self._session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise PublicNewsError(f"{url}: {exc}") from exc

    async def _eastmoney(self, instrument: InstrumentId, limit: int) -> list[NewsArticle]:
        payload = await self._get(
            "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns",
            {
                "client": "web", "biz": "web_news_col", "column": "350",
                "order": "1", "needInteractData": "0", "page_index": 1,
                "page_size": limit, "req_trace": str(uuid4()),
            },
            "https://finance.eastmoney.com/",
        )
        rows = ((payload.get("data") or {}).get("list") or []) if isinstance(payload, dict) else []
        articles = []
        for row in rows:
            try:
                published = datetime.strptime(row["showTime"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=ZoneInfo("Asia/Shanghai"),
                ).astimezone(timezone.utc)
                articles.append(NewsArticle(
                    id=f"eastmoney:{instrument.canonical}:{row['code']}", title=row["title"],
                    summary=row.get("summary") or "", url=row.get("url") or row["uniqueUrl"],
                    source=row.get("mediaName") or "东方财富", published_at=published,
                    asset_class=AssetClass.CN_EQUITY, instrument=instrument.canonical,
                    category="财经快讯",
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return articles

    async def _yahoo(self, instrument: InstrumentId, limit: int) -> list[NewsArticle]:
        payload = await self._get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            {"q": instrument.symbol, "quotesCount": 0, "newsCount": limit},
        )
        articles = []
        for row in payload.get("news") or []:
            try:
                articles.append(NewsArticle(
                    id=f"yahoo:{instrument.canonical}:{row['uuid']}", title=row["title"],
                    summary="", url=row["link"], source=row.get("publisher") or "Yahoo Finance",
                    published_at=datetime.fromtimestamp(row["providerPublishTime"], timezone.utc),
                    asset_class=AssetClass.US_EQUITY, instrument=instrument.canonical,
                    category=row.get("type") or "market",
                ))
            except (KeyError, TypeError, ValueError, OSError):
                continue
        return articles

    async def _binance(self, instrument: InstrumentId, limit: int) -> list[NewsArticle]:
        payload = await self._get(
            "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
            {"type": 1, "pageNo": 1, "pageSize": max(10, limit)},
        )
        catalogs = ((payload.get("data") or {}).get("catalogs") or []) if isinstance(payload, dict) else []
        articles = []
        for catalog in catalogs:
            for row in catalog.get("articles") or []:
                try:
                    articles.append(NewsArticle(
                        id=f"binance:{instrument.canonical}:{row['code']}", title=row["title"], summary="",
                        url=f"https://www.binance.com/en/support/announcement/detail/{row['code']}",
                        source="Binance", published_at=datetime.fromtimestamp(row["releaseDate"] / 1000, timezone.utc),
                        asset_class=AssetClass.CRYPTO, instrument=instrument.canonical,
                        category=catalog.get("catalogName") or "announcement",
                    ))
                except (KeyError, TypeError, ValueError, OSError):
                    continue
        articles.sort(key=lambda item: item.published_at, reverse=True)
        symbol = _crypto_base_symbol(instrument.symbol)
        relevant = [item for item in articles if symbol in item.title.upper()]
        return (relevant + [item for item in articles if item not in relevant])[:limit]


def _crypto_base_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "").replace("-", "")
    for quote in ("USDT", "USDC", "FDUSD", "USD", "BTC", "ETH"):
        if normalized.endswith(quote) and len(normalized) > len(quote):
            return normalized[:-len(quote)]
    return normalized


def _deduplicate(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen: set[str] = set()
    result = []
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        key = article.url.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result
