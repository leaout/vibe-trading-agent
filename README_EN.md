# Curs Vibe Trading

[中文版](README.md) | English Version

Curs is being rebuilt as a multi-market Trading Agent. Each strategy is a long-lived model conversation session: users create and revise strategies through chat, while signals, model decisions, risk checks, and order events appear on the chart and audit timeline.

The legacy Flask UI, `run.py` service entry point, first-generation service assembly, and retired trading-terminal integration have been removed. V2 is isolated from the old architecture and retains only the Eastmoney broker, market-data, database, and collection capabilities that can be migrated behind adapters.

## Current milestone

Implemented:

- A standalone FastAPI V2 control plane with health checks, OpenAPI, and a bounded SSE event stream.
- Cross-market domain models for China equities, US equities, crypto, and FX.
- Foundations for `observe / paper / live` modes and typed signal, decision, and order states.
- A React + TypeScript workspace with sessions, candlesticks, signal overlays, chat, prompt versions, and a decision timeline.
- A cpptdx HTTP adapter for China-equity snapshots, minute bars, health checks, and freshness tracking.
- An explicit "not connected" state when public market data is unavailable; the UI never replaces missing quotes with test candles.
- Durable strategy sessions, chat messages, and append-only prompt/strategy versions. SQLite is the development default; PostgreSQL is supported for production.
- Model adapters for OpenAI, DeepSeek, Claude, and OpenAI-compatible APIs. API keys are only read from environment variables.
- One-sentence strategy creation compiled into a strict allowlisted JSON schema. Missing model configuration or invalid output remains a safe draft.
- The Web workspace now uses the real Session API for creation, chat revisions, version history, pause, and resume.
- A closed-bar signal engine with allowlisted MA, EMA, RSI, MACD, ATR, VWAP, volume-ratio, comparison, and crossover rules.
- Running sessions scan the latest closed bars every five seconds; candidate signals are persisted and deduplicated by strategy version and bar.
- Candidate signals update through SSE and appear on the candlestick overlay and decision timeline.
- A system-owned Paper Broker that creates a default CNY 1,000,000 account on first start and binds it to strategy sessions.
- Paper market fills, cash ledger, positions, orders, fills, fees, signal idempotency, position caps, and China-equity T+1 checks.
- One-click paper-mode activation in the Web UI with equity, cash, PnL, latest order, fill, and rejection status.

Not implemented yet:

- Limit-order matching, partial fills, configurable fee schedules, an Eastmoney V2 adapter, and live execution.
- Public multi-market market data: cpptdx/Eastmoney fallback for China equities, Yahoo Finance for US equities, and Binance for crypto.
- Model trading decisions after candidate signals, limit-order matching, and a complete audit-event journal.

This version is for architecture and UI integration. It must not be used for live automated trading.

## Repository layout

```text
trading_v2/       # Standalone FastAPI, domain models, events, market APIs
web_v2/           # React + TypeScript Vibe Trading workspace
docs/v2/          # Architecture, data model, API, and lifecycle documents
curs/broker/      # Retained Eastmoney broker capability
curs/collection/  # Retained data collection capabilities
data_collection/  # Daily hot-stock collection and import
test/             # V2 and retained-module tests
```

## Installation

Backend:

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
Copy-Item .env.v2.example .env
```

Frontend:

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm install
```

Keep secrets in `config.local.yml`, environment variables, or a secret manager. Never commit API keys, broker passwords, or session files.

## Running

Start the V2 backend:

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m trading_v2
```

Default endpoints:

- API: `http://127.0.0.1:8010/api/v2`
- OpenAPI: `http://127.0.0.1:8010/docs`
- cpptdx: `http://127.0.0.1:8022`

### Public market data

The default is `TRADING_V2_MARKET_DATA_PROVIDER=public`: cpptdx, then Eastmoney/Sina fallback for China equities, Yahoo Finance Chart for US equities, and Binance Spot public data for crypto. Examples: `us_equity:XNAS:AAPL` and `crypto:BINANCE:BTCUSDT`. These sources are for quotes and paper trading only, do not require API keys, and are subject to rate limits, regional restrictions, and limited intraday history.

Start the V2 frontend:

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to port 8010.

The first page is a login screen. Authentication is enabled by default: click “首次使用？创建账户” on the first launch to create the local administrator, then sign in with the username and password. Passwords are stored only as PBKDF2 hashes and login state uses an HttpOnly cookie; strategy, market, paper-account, and SSE endpoints require authentication. Set `TRADING_V2_AUTH_ENABLED=false` only for temporary test or trusted internal deployments.

Use the sun/moon button in the top-right corner to switch between light and dark themes. The preference is stored locally in the browser.

## Database and strategy sessions

Without database configuration, the service uses `data/trading_v2.db` and runs immediately. PostgreSQL is recommended in production:

```dotenv
TRADING_V2_DATABASE_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/curs_trading
```

The service automatically creates session, message, strategy-version, candidate-signal, and paper-trading tables including `paper_accounts_v2`, `paper_positions_v2`, `paper_orders_v2`, `paper_fills_v2`, and `paper_ledger_v2`. Schema migrations will be added before live trading is enabled.

Once a valid strategy is resumed into the running state, the background scanner fetches market data and only evaluates bars with `is_closed=true`. One scan can also be requested manually:

```http
POST /api/v2/sessions/{session_id}/evaluate
```

Only one candidate is stored for the same session, strategy version, instrument, timeframe, bar close, and side. Observe mode only records it. Once paper mode is enabled in the UI and the strategy is running, deterministic cash, position-cap, and T+1 checks route the signal to the system Paper Broker. This is currently `rule_only`; an AI trading decision is not invoked yet.

The default system account starts with CNY 1,000,000. Multiple internal accounts can also be created through the API:

```http
GET  /api/v2/paper/accounts
POST /api/v2/paper/accounts
POST /api/v2/paper/sessions/{session_id}/enable
GET  /api/v2/paper/sessions/{session_id}
```

## Model configuration

DeepSeek:

```dotenv
TRADING_V2_MODEL_ENABLED=true
TRADING_V2_MODEL_PROVIDER=deepseek
TRADING_V2_MODEL_NAME=deepseek-chat
TRADING_V2_MODEL_API_KEY_ENV=DEEPSEEK_API_KEY
DEEPSEEK_API_KEY=your-secret
```

For OpenAI, use `openai / gpt-5` with `OPENAI_API_KEY`. For Claude, use `anthropic / claude-sonnet-4-5` with `ANTHROPIC_API_KEY`. For a compatible Chat Completions service, select `openai_compatible` and set `TRADING_V2_MODEL_BASE_URL`.

The model only compiles conversation input into a constrained strategy representation. It has no broker, order, or publication authority. Every new strategy currently stays in draft/observe mode.

## cpptdx

Configure it through `.env`:

```dotenv
TRADING_V2_CPPTDX_BASE_URL=http://127.0.0.1:8022
TRADING_V2_CPPTDX_TIMEOUT_SECONDS=3
```

Available endpoints:

- `GET /api/v2/market/status`
- `GET /api/v2/market/bars?instrument=cn_equity:XSHG:600000&timeframe=5m&limit=200`
- `POST /api/v2/market/snapshots`

cpptdx is used for China-equity minute bars, snapshots, and gap filling. It does not execute broker orders.

## Broker configuration

The retired trading terminal and its SDK have been fully removed from code, dependencies, and configuration. The retained Eastmoney code lives under `curs/broker/`. Its V2 adapter is not wired yet, so configuring it does not grant V2 order authority.

Example:

```yaml
broker: eastmoney

eastmoney:
  account_no: ""
  password: ""
  session_file: "data/eastmoney_trader.session"
```

Eastmoney depends on a web trading interface and may break when its API or login checks change. Begin with a read-only connection test, then validate with paper or approval mode. Future markets will use new standard broker adapters instead of retaining compatibility with the removed terminal integration.

## Tests

```powershell
# V2
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_trading_v2*.py" -v

# Frontend production build
cd web_v2
npm run build
```

## Documentation

- [V2 architecture](docs/v2/ARCHITECTURE.md)
- [V2 data model](docs/v2/DATA_MODEL.md)
- [V2 API](docs/v2/API.md)
- [V2 trading lifecycle](docs/v2/TRADING_LIFECYCLE.md)
- [中文文档](README.md)
