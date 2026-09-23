# coding: utf-8
"""Public, keyless market-data adapters for the V2 paper environment.

The provider deliberately uses HTTP only and normalizes every upstream into the
same ``Bar``/``MarketSnapshot`` contract.  It is suitable for paper trading,
not for latency-sensitive live execution.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any, Sequence

import aiohttp

from trading_v2.domain.enums import AssetClass
from trading_v2.domain.market import Bar, InstrumentId, MarketSnapshot
from trading_v2.market.cpptdx import CppTdxError, CppTdxMarketDataProvider
from trading_v2.market.provider import MarketDataHealth


class PublicMarketDataError(RuntimeError):
    """An upstream public market-data request failed."""


_YAHOO_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "1d": "1d"}
_BINANCE_INTERVALS = {**_YAHOO_INTERVALS, "1h": "1h"}
_EASTMONEY_KLT = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 101}


class PublicMarketDataProvider:
    """Route CN/US/crypto instruments to public market-data endpoints.

    CN equities use cpptdx first and Eastmoney's public quote/K-line endpoint
    as a fallback. US equities use Yahoo's chart endpoint. Crypto uses
    Binance's public data endpoint (no API key or account is required).
    """

    def __init__(self, cpptdx: CppTdxMarketDataProvider, timeout_seconds: float = 8.0, snapshot_interval_ms: int = 2_000):
        self.cpptdx = cpptdx
        self.timeout_seconds = timeout_seconds
        self.snapshot_interval_ms = snapshot_interval_ms
        self._session: aiohttp.ClientSession | None = None

    async def health(self) -> MarketDataHealth:
        started = perf_counter()
        sources: list[str] = []
        details: list[str] = []
        try:
            cpptdx = await self.cpptdx.health()
            if cpptdx.healthy:
                sources.append("cpptdx")
            else:
                details.append(f"cpptdx: {cpptdx.detail}")
        except Exception as exc:
            details.append(f"cpptdx: {exc}")
        try:
            await self._get("https://data-api.binance.vision/api/v3/ping", {})
            sources.append("binance")
        except Exception as exc:
            details.append(f"binance: {exc}")
        try:
            await self._get("https://query1.finance.yahoo.com/v8/finance/chart/SPY", {"range": "1d", "interval": "1d"})
            sources.append("yahoo")
        except Exception as exc:
            details.append(f"yahoo: {exc}")
        healthy = bool(sources)
        return MarketDataHealth(
            healthy=healthy,
            source="public:" + "+".join(sources or ["none"]),
            latency_ms=round((perf_counter() - started) * 1000, 2),
            detail="; ".join(details) if details else "public market data available",
        )

    async def get_bars(self, instrument: InstrumentId, timeframe: str, limit: int, provider: str = "auto") -> list[Bar]:
        if not 1 <= limit <= 800:
            raise ValueError("limit must be between 1 and 800")
        if timeframe not in _YAHOO_INTERVALS:
            raise ValueError(f"unsupported public timeframe: {timeframe}")
        if instrument.asset_class == AssetClass.CN_EQUITY:
            if provider == "sina":
                return await self._sina_bars(instrument, timeframe, limit)
            if provider == "eastmoney":
                return await self._eastmoney_bars(instrument, timeframe, limit)
            try:
                return await self.cpptdx.get_bars(instrument, timeframe, limit)
            except Exception:
                if provider == "cpptdx":
                    raise
                return await self._eastmoney_bars(instrument, timeframe, limit)
        if instrument.asset_class == AssetClass.US_EQUITY:
            if provider not in {"auto", "public", "yahoo"}:
                raise ValueError("US equities require public/yahoo provider")
            return await self._yahoo_bars(instrument, timeframe, limit)
        if instrument.asset_class == AssetClass.CRYPTO:
            if provider not in {"auto", "public", "binance"}:
                raise ValueError("crypto requires public/binance provider")
            return await self._binance_bars(instrument, timeframe, limit)
        raise ValueError(f"no public provider configured for {instrument.asset_class.value}")

    async def get_snapshots(self, instruments: Sequence[InstrumentId], provider: str = "auto") -> list[MarketSnapshot]:
        result: list[MarketSnapshot] = []
        for instrument in instruments:
            if instrument.asset_class == AssetClass.CN_EQUITY:
                if provider == "sina":
                    result.append(await self._sina_snapshot(instrument))
                    continue
                if provider == "eastmoney":
                    result.append(await self._eastmoney_snapshot(instrument))
                    continue
                try:
                    result.extend(await self.cpptdx.get_snapshots([instrument]))
                    continue
                except Exception:
                    if provider == "cpptdx":
                        raise
                    result.append(await self._eastmoney_snapshot(instrument))
            elif instrument.asset_class == AssetClass.US_EQUITY:
                result.append(await self._yahoo_snapshot(instrument))
            elif instrument.asset_class == AssetClass.CRYPTO:
                result.append(await self._binance_snapshot(instrument))
            else:
                raise ValueError(f"no public provider configured for {instrument.asset_class.value}")
        return result

    async def stream_snapshots(self, instruments: Sequence[InstrumentId]):
        while True:
            for snapshot in await self.get_snapshots(instruments):
                yield snapshot
            await asyncio.sleep(self.snapshot_interval_ms / 1000)

    async def close(self) -> None:
        await self.cpptdx.close()
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _get(self, url: str, params: dict[str, Any]) -> Any:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds))
        try:
            async with self._session.get(url, params=params, headers={"User-Agent": "vibe-trading-agent/0.1"}) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise PublicMarketDataError(f"{url}: {exc}") from exc

    async def _yahoo_payload(self, instrument: InstrumentId, timeframe: str, limit: int) -> dict[str, Any]:
        interval = _YAHOO_INTERVALS[timeframe]
        period = "2y" if timeframe == "1d" else ("60d" if timeframe != "1m" else "7d")
        payload = await self._get(f"https://query1.finance.yahoo.com/v8/finance/chart/{instrument.symbol}", {"range": period, "interval": interval, "events": "div,splits"})
        try:
            return payload["chart"]["result"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise PublicMarketDataError("Yahoo returned no chart data") from exc

    async def _yahoo_bars(self, instrument: InstrumentId, timeframe: str, limit: int) -> list[Bar]:
        result = await self._yahoo_payload(instrument, timeframe, limit)
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        now = datetime.now(timezone.utc)
        duration = _duration(timeframe)
        bars: list[Bar] = []
        for index, timestamp in enumerate(timestamps):
            values = {key: (quote.get(key) or [None] * len(timestamps))[index] for key in ("open", "high", "low", "close", "volume")}
            if any(values[key] is None for key in ("open", "high", "low", "close")):
                continue
            opened = datetime.fromtimestamp(timestamp, timezone.utc)
            bars.append(Bar(instrument=instrument, timeframe=timeframe, open_time=opened, close_time=opened + duration, open=_decimal(values["open"]), high=_decimal(values["high"]), low=_decimal(values["low"]), close=_decimal(values["close"]), volume=_decimal(values["volume"] or 0), source="yahoo", is_closed=now >= opened + duration, received_at=now))
        return bars[-limit:]

    async def _yahoo_snapshot(self, instrument: InstrumentId) -> MarketSnapshot:
        bars = await self._yahoo_bars(instrument, "1d", 2)
        if not bars:
            raise PublicMarketDataError(f"no Yahoo quote for {instrument.symbol}")
        latest = bars[-1]
        previous = bars[-2].close if len(bars) > 1 else latest.close
        return _snapshot(instrument, latest.close, latest.open, latest.high, latest.low, previous, latest.volume, latest.turnover or Decimal("0"), "yahoo", latest.open_time)

    async def _binance_bars(self, instrument: InstrumentId, timeframe: str, limit: int) -> list[Bar]:
        symbol = instrument.symbol.replace("/", "").replace("-", "")
        payload = await self._get("https://data-api.binance.vision/api/v3/klines", {"symbol": symbol, "interval": _BINANCE_INTERVALS[timeframe], "limit": limit})
        now = datetime.now(timezone.utc)
        duration = _duration(timeframe)
        bars = []
        for row in payload:
            opened = datetime.fromtimestamp(int(row[0]) / 1000, timezone.utc)
            bars.append(Bar(instrument=instrument, timeframe=timeframe, open_time=opened, close_time=opened + duration, open=_decimal(row[1]), high=_decimal(row[2]), low=_decimal(row[3]), close=_decimal(row[4]), volume=_decimal(row[5]), turnover=_decimal(row[7]), source="binance", is_closed=now >= opened + duration, received_at=now))
        return bars

    async def _binance_snapshot(self, instrument: InstrumentId) -> MarketSnapshot:
        symbol = instrument.symbol.replace("/", "").replace("-", "")
        raw = await self._get("https://data-api.binance.vision/api/v3/ticker/24hr", {"symbol": symbol})
        now = datetime.now(timezone.utc)
        return _snapshot(instrument, _decimal(raw["lastPrice"]), _decimal(raw["openPrice"]), _decimal(raw["highPrice"]), _decimal(raw["lowPrice"]), _decimal(raw.get("prevClosePrice") or raw["openPrice"]), _decimal(raw["volume"]), _decimal(raw["quoteVolume"]), "binance", now)

    async def _eastmoney_bars(self, instrument: InstrumentId, timeframe: str, limit: int) -> list[Bar]:
        secid = _eastmoney_secid(instrument)
        payload = await self._get("https://push2his.eastmoney.com/api/qt/stock/kline/get", {"secid": secid, "klt": _EASTMONEY_KLT[timeframe], "fqt": 1, "beg": 0, "end": 20500101, "lmt": limit})
        rows = (payload.get("data") or {}).get("klines") or []
        if not rows:
            return await self._sina_bars(instrument, timeframe, limit)
        now = datetime.now(timezone.utc)
        duration = _duration(timeframe)
        bars = []
        for row in rows:
            parts = row.split(",")
            opened = datetime.fromisoformat(parts[0]).replace(tzinfo=timezone.utc)
            bars.append(Bar(instrument=instrument, timeframe=timeframe, open_time=opened, close_time=opened + duration, open=_decimal(parts[1]), close=_decimal(parts[2]), high=_decimal(parts[3]), low=_decimal(parts[4]), volume=_decimal(parts[5]), turnover=_decimal(parts[6]), source="eastmoney", is_closed=now >= opened + duration, received_at=now))
        return bars[-limit:]

    async def _eastmoney_snapshot(self, instrument: InstrumentId) -> MarketSnapshot:
        raw = (await self._get("https://push2.eastmoney.com/api/qt/stock/get", {"secid": _eastmoney_secid(instrument), "fields": "f43,f44,f45,f46,f47,f48,f60,f58,f57"})).get("data") or {}
        if not raw:
            return await self._sina_snapshot(instrument)
        now = datetime.now(timezone.utc)
        return _snapshot(instrument, _decimal(raw["f43"]) / 100, _decimal(raw["f46"]) / 100, _decimal(raw["f44"]) / 100, _decimal(raw["f45"]) / 100, _decimal(raw["f60"]) / 100, _decimal(raw.get("f47") or 0), _decimal(raw.get("f48") or 0), "eastmoney", now)

    async def _sina_bars(self, instrument: InstrumentId, timeframe: str, limit: int) -> list[Bar]:
        scale = {"1m": 5, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 240}[timeframe]
        payload = await self._get("http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData", {"symbol": _sina_symbol(instrument), "scale": scale, "ma": "no", "datalen": limit})
        now = datetime.now(timezone.utc)
        duration = _duration(timeframe)
        bars = []
        for raw in payload or []:
            opened = datetime.fromisoformat(raw["day"]).replace(tzinfo=timezone.utc)
            bars.append(Bar(instrument=instrument, timeframe=timeframe, open_time=opened, close_time=opened + duration, open=_decimal(raw["open"]), high=_decimal(raw["high"]), low=_decimal(raw["low"]), close=_decimal(raw["close"]), volume=_decimal(raw.get("volume") or 0), source="sina", is_closed=now >= opened + duration, received_at=now))
        return bars[-limit:]

    async def _sina_snapshot(self, instrument: InstrumentId) -> MarketSnapshot:
        text = await self._get_text("http://hq.sinajs.cn/list=" + _sina_symbol(instrument))
        values = text.split(",")
        if len(values) < 32:
            raise PublicMarketDataError("Sina returned no quote")
        now = datetime.now(timezone.utc)
        last, prev = _decimal(values[3]), _decimal(values[2])
        return _snapshot(instrument, last, _decimal(values[1]), _decimal(values[4]), _decimal(values[5]), prev, _decimal(values[8]), _decimal(values[9]), "sina", now)

    async def _get_text(self, url: str) -> str:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds))
        try:
            async with self._session.get(url, headers={"User-Agent": "vibe-trading-agent/0.1", "Referer": "https://finance.sina.com.cn/"}) as response:
                response.raise_for_status()
                return await response.text(encoding="gbk")
        except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError) as exc:
            raise PublicMarketDataError(f"{url}: {exc}") from exc


def _duration(timeframe: str) -> timedelta:
    return {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "15m": timedelta(minutes=15), "30m": timedelta(minutes=30), "1h": timedelta(hours=1), "1d": timedelta(days=1)}[timeframe]


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _snapshot(instrument, last, opened, high, low, previous, volume, turnover, source, market_time):
    return MarketSnapshot(instrument=instrument, last=last, open=opened, high=high, low=low, prev_close=previous, volume=volume, turnover=turnover, market_time=market_time, received_at=datetime.now(timezone.utc), source=source)


def _eastmoney_secid(instrument: InstrumentId) -> str:
    market = "1" if instrument.venue == "XSHG" else "0"
    return f"{market}.{instrument.symbol}"


def _sina_symbol(instrument: InstrumentId) -> str:
    prefix = "sh" if instrument.venue == "XSHG" else "sz"
    return prefix + instrument.symbol
