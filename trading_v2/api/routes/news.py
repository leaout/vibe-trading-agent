# coding: utf-8
"""Provider-neutral financial-news endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from trading_v2.api.dependencies import get_news_service
from trading_v2.api.routes.market import parse_instrument
from trading_v2.news.models import NewsArticle
from trading_v2.news.service import NewsService
from trading_v2.news.public import PublicNewsError

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsArticle])
async def financial_news(
    news: Annotated[NewsService, Depends(get_news_service)],
    instrument: str = Query(description="asset_class:venue:symbol"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[NewsArticle]:
    try:
        articles, _ = await news.refresh(parse_instrument(instrument), limit)
        return articles
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PublicNewsError as exc:
        raise HTTPException(status_code=502, detail=f"financial news unavailable: {exc}") from exc
