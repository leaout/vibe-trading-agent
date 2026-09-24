# coding: utf-8
"""Poll public news sources and fan new items out as internal events."""

import asyncio
import logging

from trading_v2.domain.market import InstrumentId
from trading_v2.events import InMemoryEventStream
from trading_v2.news.service import NewsService
from trading_v2.sessions.service import TradingSessionService
from trading_v2.signals.runtime import _parse_instrument

logger = logging.getLogger(__name__)


class NewsRuntime:
    def __init__(self, sessions: TradingSessionService, service: NewsService,
                 events: InMemoryEventStream, poll_interval_seconds: float = 60) -> None:
        self.sessions = sessions
        self.service = service
        self.events = events
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="financial-news-runtime")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def refresh_once(self) -> int:
        async with self._lock:
            targets = await self.sessions.runtime_targets()
            groups: dict[str, tuple[InstrumentId, set[str]]] = {}
            for session, _, strategy in targets:
                instrument = _parse_instrument(strategy.instrument)
                if instrument.canonical not in groups:
                    groups[instrument.canonical] = (instrument, set())
                groups[instrument.canonical][1].add(session.id)
            published = 0
            for instrument, session_ids in groups.values():
                _, created = await self.service.refresh(instrument)
                if not created:
                    continue
                for session_id in session_ids:
                    latest = created[0]
                    await self.events.publish("news.received", {
                        "session_id": session_id, "instrument": instrument.canonical,
                        "count": len(created), "article_ids": [item.id for item in created],
                        "title": latest.title, "source": latest.source,
                        "published_at": latest.published_at.isoformat(),
                    })
                    published += len(created)
            return published

    async def _run(self) -> None:
        while True:
            try:
                await self.refresh_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("financial news refresh failed")
            await asyncio.sleep(self.poll_interval_seconds)
