# Vibe Trading Agent

[中文](README.md) | English

Vibe Trading Agent is a multi-market trading agent for China equities, US equities, and crypto. Each strategy is a long-lived session: users create and revise it in natural language, the system continuously reads market data, produces candidates from closed bars, asks a model to review them with recent financial news, and passes approved decisions to deterministic risk controls and the system paper account.

> The current release supports observation and paper trading only. Live automated execution is not available.

## Available today

- React + TypeScript workspace with candlesticks, signal markers, strategy chat, prompt versions, decision events, and light/dark themes.
- FastAPI service with authentication, strategy sessions, SSE events, market data, news, model decisions, and paper accounts.
- Public market data: cpptdx/Eastmoney/Sina for China equities, Yahoo Finance for US equities, and Binance for crypto.
- Minute, hourly, daily, weekly, monthly, yearly, and all-history chart periods.
- DeepSeek, OpenAI, Claude, and OpenAI-compatible model adapters.
- System Paper Broker with cash, positions, orders, fills, fees, position limits, signal idempotency, and China-equity T+1.
- Financial news from Eastmoney, Yahoo Finance, and official Binance announcements.
- Decision audits persist the strategy, indicators, news, model input/output, and paper execution; click a chart signal to inspect it.

## Decision flow

```text
Natural-language strategy
  → constrained strategy version
  → closed bars and technical indicators
  → candidate BUY / SELL signal
  → model reviews recent news and returns BUY / SELL / HOLD
  → deterministic cash, position, and T+1 checks
  → paper fill or rejection
```

News is subscribed, persisted, and deduplicated per session instrument. When a candidate appears, the service includes up to eight items from the previous 48 hours as temporary context. News is not appended to normal chat history and cannot place an order by itself. The model cannot size orders, bypass risk controls, or access a broker. Failures, timeouts, low confidence, and invalid output safely become `HOLD`.

## Quick start

Requirements: Python 3.10+ and Node.js 20+.

```powershell
cd E:\pro\curs-trading-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
Copy-Item .env.v2.example .env
Copy-Item .env.local.example .env.local

cd web_v2
npm install
```

Start the backend:

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m trading_v2
```

Start the frontend:

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm run dev
```

Open:

- Web: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8010/api/v2`
- OpenAPI: `http://127.0.0.1:8010/docs`

Create the local administrator on the first visit. Passwords are stored as PBKDF2 hashes and login state uses an HttpOnly cookie. Both `.env` and `.env.local` are ignored by Git; never force-add them or commit API keys, broker passwords, or session files.

## Model configuration

Copy `.env.local.example` to `.env.local`, then add the key only on this machine:

```dotenv
TRADING_V2_MODEL_ENABLED=true
TRADING_V2_MODEL_PROVIDER=deepseek
TRADING_V2_MODEL_NAME=deepseek-chat
TRADING_V2_MODEL_API_KEY_ENV=DEEPSEEK_API_KEY
DEEPSEEK_API_KEY=your-secret
```

Precedence is process environment → `.env.local` → `.env` → built-in defaults. Keep ordinary runtime settings in `.env` and all secrets in `.env.local`. Tracked `*.example` files must contain placeholders only.

Other providers:

| Provider | `TRADING_V2_MODEL_PROVIDER` | Example key variable |
|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Claude | `anthropic` | `ANTHROPIC_API_KEY` |
| OpenAI-compatible | `openai_compatible` | Custom; also set `TRADING_V2_MODEL_BASE_URL` |

Use “决策模型” in the lower-left sidebar to inspect the configuration and run a no-trade connection test.

## Data and news

The default database is `data/trading_v2.db`. Set `TRADING_V2_DATABASE_URL` to use PostgreSQL in production.

Public market and news sources require no API key, but may be affected by rate limits, regional restrictions, and limited history windows. Missing market data is reported explicitly; the UI never substitutes test candles. News is refreshed every 60 seconds by default. See [.env.v2.example](.env.v2.example) for related settings.

Example instruments:

- China equity: `cn_equity:XSHG:600519`
- US equity: `us_equity:XNAS:AAPL`
- Crypto: `crypto:BINANCE:BTCUSDT`

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_trading_v2*.py" -v

cd web_v2
npm run build
```

## Repository layout

```text
trading_v2/  Backend, strategy sessions, market data, news, decisions, and paper trading
web_v2/      React workspace
docs/v2/     Architecture, data model, API, and trading lifecycle
test/        V2 automated tests
```

## Documentation

- [Architecture](docs/v2/ARCHITECTURE.md)
- [Trading lifecycle](docs/v2/TRADING_LIFECYCLE.md)
- [API](docs/v2/API.md)
- [Data model](docs/v2/DATA_MODEL.md)
- [中文 README](README.md)
