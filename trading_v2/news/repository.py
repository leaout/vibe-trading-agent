# coding: utf-8
"""Durable, deduplicated storage for normalized financial news."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from trading_v2.domain.enums import AssetClass
from trading_v2.news.models import NewsArticle
from trading_v2.storage.database import Base, Database


class NewsRecord(Base):
    __tablename__ = "financial_news_v2"
    __table_args__ = (
        UniqueConstraint("instrument", "url", name="uq_financial_news_instrument_url"),
    )

    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1_000))
    source: Mapped[str] = mapped_column(String(100))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    asset_class: Mapped[str] = mapped_column(String(30), index=True)
    instrument: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NewsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_many(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        if not articles:
            return []
        ids = [article.id for article in articles]
        urls = [article.url for article in articles]
        now = datetime.now(timezone.utc)
        try:
            with self.database.sessions.begin() as db:
                existing_ids = set(db.scalars(select(NewsRecord.id).where(NewsRecord.id.in_(ids))).all())
                existing_pairs = set(db.execute(
                    select(NewsRecord.instrument, NewsRecord.url).where(NewsRecord.url.in_(urls))
                ).all())
                created = [
                    article for article in articles
                    if article.id not in existing_ids
                    and (article.instrument, article.url) not in existing_pairs
                ]
                for article in created:
                    db.add(NewsRecord(
                        id=article.id, title=article.title, summary=article.summary,
                        url=article.url, source=article.source,
                        published_at=article.published_at, asset_class=article.asset_class.value,
                        instrument=article.instrument, category=article.category, received_at=now,
                    ))
                return created
        except IntegrityError:
            return []

    def list_for_instrument(
        self, instrument: str, limit: int = 20, max_age_hours: int | None = None,
    ) -> list[NewsArticle]:
        with self.database.sessions() as db:
            query = select(NewsRecord).where(NewsRecord.instrument == instrument)
            if max_age_hours is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
                query = query.where(NewsRecord.published_at >= cutoff)
            rows = db.scalars(query.order_by(NewsRecord.published_at.desc()).limit(limit)).all()
        return [self._model(row) for row in rows]

    @staticmethod
    def _model(row: NewsRecord) -> NewsArticle:
        published_at = row.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return NewsArticle(
            id=row.id, title=row.title, summary=row.summary, url=row.url,
            source=row.source, published_at=published_at,
            asset_class=AssetClass(row.asset_class), instrument=row.instrument,
            category=row.category,
        )
