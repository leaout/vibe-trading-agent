# coding: utf-8
"""Provider-neutral financial-news adapters."""

from trading_v2.news.models import NewsArticle
from trading_v2.news.public import PublicNewsError, PublicNewsProvider
from trading_v2.news.service import NewsService

__all__ = ["NewsArticle", "NewsService", "PublicNewsError", "PublicNewsProvider"]
