# coding: utf-8
"""Financial-news provider boundary."""

from typing import Protocol

from trading_v2.domain.market import InstrumentId
from trading_v2.news.models import NewsArticle


class NewsProvider(Protocol):
    async def get_news(self, instrument: InstrumentId, limit: int = 20) -> list[NewsArticle]:
        ...

    async def close(self) -> None:
        ...
