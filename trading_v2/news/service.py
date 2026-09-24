# coding: utf-8
"""News ingestion and bounded AI-context service."""

import asyncio

from trading_v2.domain.market import InstrumentId
from trading_v2.news.models import NewsArticle
from trading_v2.news.provider import NewsProvider
from trading_v2.news.repository import NewsRepository


class NewsService:
    def __init__(self, provider: NewsProvider, repository: NewsRepository) -> None:
        self.provider = provider
        self.repository = repository

    async def refresh(self, instrument: InstrumentId, limit: int = 20) -> tuple[list[NewsArticle], list[NewsArticle]]:
        upstream = await self.provider.get_news(instrument, limit)
        created = await asyncio.to_thread(self.repository.save_many, upstream)
        stored = await asyncio.to_thread(
            self.repository.list_for_instrument, instrument.canonical, limit,
        )
        return stored, created

    async def list_news(self, instrument: InstrumentId, limit: int = 20) -> list[NewsArticle]:
        return await asyncio.to_thread(
            self.repository.list_for_instrument, instrument.canonical, limit,
        )

    async def decision_context(
        self, instrument: InstrumentId, limit: int = 8, max_age_hours: int = 48,
    ) -> list[dict[str, str]]:
        articles = await asyncio.to_thread(
            self.repository.list_for_instrument,
            instrument.canonical, limit, max_age_hours,
        )
        return [{
            "title": article.title,
            "summary": article.summary[:500],
            "source": article.source,
            "published_at": article.published_at.isoformat(),
            "category": article.category,
        } for article in articles]

    async def close(self) -> None:
        await self.provider.close()
