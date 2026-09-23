import type {
  AgentEvent,
  AuthUser,
  Candle,
  ChatMessage,
  ChartSignal,
  PaperAccountDetail,
  SessionSnapshot,
  StrategyPromptVersion,
  TradingSession,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v2";

interface ApiBar {
  open_time: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: string | number;
  source: string;
}

interface ApiSession {
  id: string;
  name: string;
  symbol: string;
  venue: string;
  asset_class: string;
  timeframe: string;
  status: TradingSession["status"];
  mode: TradingSession["mode"];
  pnl_percent: number;
  prompt_version: number;
  created_at: string;
  updated_at: string;
}

interface ApiUser { id: string; username: string; created_at: string; }
interface ApiAuthStatus { authenticated: boolean; user?: ApiUser | null; }

interface ApiMessage {
  id: string;
  session_id: string;
  role: ChatMessage["role"];
  content: string;
  created_at: string;
  version?: number;
  status?: "complete" | "failed";
}

interface ApiPromptVersion {
  version: number;
  summary: string;
  strategy?: Record<string, unknown>;
  active: boolean;
  warning?: string;
  created_at: string;
}

interface ApiSessionSnapshot {
  session: ApiSession;
  messages: ApiMessage[];
  prompt_versions: ApiPromptVersion[];
  signals: ApiSignal[];
  events: ApiEvent[];
}

interface ApiSignal {
  id: string;
  timestamp: string;
  price: number;
  side: ChartSignal["side"];
  state: ChartSignal["state"];
  label: string;
  confidence?: number;
}

interface ApiEvent {
  id: string;
  timestamp: string;
  type: AgentEvent["type"];
  title: string;
  detail: string;
  state: AgentEvent["state"];
  duration_ms?: number;
}

interface ApiPaperDetail {
  account: {
    id: string; name: string; currency: string; initial_cash: string | number;
    cash: string | number; market_value: string | number; total_equity: string | number;
    realized_pnl: string | number; unrealized_pnl: string | number;
  };
  positions: Array<{
    instrument: string; quantity: string | number; available_quantity: string | number;
    average_cost: string | number; last_price: string | number;
    market_value: string | number; unrealized_pnl: string | number;
  }>;
  orders: Array<{
    id: string; signal_id: string; side: "buy" | "sell"; instrument: string; quantity: string | number;
    price: string | number; fee: string | number; status: "filled" | "rejected";
    rejection_reason?: string; created_at: string;
  }>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = await response.text();
    }
    throw new ApiError(`请求失败：${response.status}`, response.status, payload);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const mapUser = (user: ApiUser): AuthUser => ({
  id: user.id, username: user.username, createdAt: user.created_at,
});

const formatActivity = (value: string) => new Date(value).toLocaleString("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const mapSession = (session: ApiSession): TradingSession => ({
  id: session.id,
  name: session.name,
  symbol: session.symbol,
  venue: session.venue,
  assetClass: session.asset_class,
  timeframe: session.timeframe,
  status: session.status,
  mode: session.mode,
  pnlPercent: session.pnl_percent,
  lastActivity: formatActivity(session.updated_at),
  promptVersion: session.prompt_version,
});

const mapMessage = (message: ApiMessage): ChatMessage => ({
  id: message.id,
  role: message.role,
  content: message.content,
  timestamp: new Date(message.created_at).toLocaleTimeString("zh-CN", {
    hour: "2-digit", minute: "2-digit", hour12: false,
  }),
  version: message.version,
  status: message.status,
});

const mapVersion = (version: ApiPromptVersion): StrategyPromptVersion => ({
  version: version.version,
  summary: version.summary,
  strategy: version.strategy,
  warning: version.warning,
  createdAt: formatActivity(version.created_at),
  active: version.active,
});

const mapSignal = (signal: ApiSignal): ChartSignal => ({
  id: signal.id,
  timestamp: Date.parse(signal.timestamp),
  price: Number(signal.price),
  side: signal.side,
  state: signal.state,
  label: signal.label,
  confidence: signal.confidence,
});

const mapEvent = (event: ApiEvent): AgentEvent => ({
  id: event.id,
  timestamp: new Date(event.timestamp).toLocaleTimeString("zh-CN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }),
  type: event.type,
  title: event.title,
  detail: event.detail,
  state: event.state,
  durationMs: event.duration_ms,
});

const mapSnapshot = (snapshot: ApiSessionSnapshot): SessionSnapshot => ({
  session: mapSession(snapshot.session),
  messages: snapshot.messages.map(mapMessage),
  promptVersions: snapshot.prompt_versions.map(mapVersion),
  candles: [],
  signals: snapshot.signals.map(mapSignal),
  events: snapshot.events.map(mapEvent),
});

const mapPaperDetail = (detail: ApiPaperDetail): PaperAccountDetail => ({
  account: {
    id: detail.account.id, name: detail.account.name, currency: detail.account.currency,
    initialCash: Number(detail.account.initial_cash), cash: Number(detail.account.cash),
    marketValue: Number(detail.account.market_value), totalEquity: Number(detail.account.total_equity),
    realizedPnl: Number(detail.account.realized_pnl), unrealizedPnl: Number(detail.account.unrealized_pnl),
  },
  positions: detail.positions.map((position) => ({
    instrument: position.instrument, quantity: Number(position.quantity),
    availableQuantity: Number(position.available_quantity), averageCost: Number(position.average_cost),
    lastPrice: Number(position.last_price), marketValue: Number(position.market_value),
    unrealizedPnl: Number(position.unrealized_pnl),
  })),
  orders: detail.orders.map((order) => ({
    id: order.id, signalId: order.signal_id, side: order.side, instrument: order.instrument,
    quantity: Number(order.quantity), price: Number(order.price), fee: Number(order.fee),
    status: order.status, rejectionReason: order.rejection_reason, createdAt: order.created_at,
  })),
});

export const apiClient = {
  getAuthStatus: async () => {
    const status = await request<ApiAuthStatus>("/auth/me");
    return status.user ? mapUser(status.user) : null;
  },
  login: async (username: string, password: string) => mapUser(await request<ApiUser>("/auth/login", {
    method: "POST", body: JSON.stringify({ username, password }),
  })),
  register: async (username: string, password: string) => mapUser(await request<ApiUser>("/auth/register", {
    method: "POST", body: JSON.stringify({ username, password }),
  })),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  getSessions: async () => (await request<ApiSession[]>("/sessions")).map(mapSession),
  createSession: async (message: string) =>
    mapSession(await request<ApiSession>("/sessions", {
      method: "POST",
      body: JSON.stringify({ message }),
    })),
  getSession: async (sessionId: string) =>
    mapSnapshot(await request<ApiSessionSnapshot>(`/sessions/${encodeURIComponent(sessionId)}`)),
  getCandles: (sessionId: string, timeframe: string) =>
    request<Candle[]>(
      `/sessions/${encodeURIComponent(sessionId)}/candles?timeframe=${encodeURIComponent(timeframe)}`,
    ),
  getMarketBars: async (instrument: string, timeframe: string, limit = 200, provider = "auto") => {
    const query = new URLSearchParams({
      instrument,
      timeframe: timeframe === "1D" ? "1d" : timeframe,
      limit: String(limit),
      provider,
    });
    const bars = await request<ApiBar[]>(`/market/bars?${query.toString()}`);
    return bars.map((bar) => ({
      timestamp: Date.parse(bar.open_time),
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
      volume: Number(bar.volume),
      source: bar.source,
    } satisfies Candle));
  },
  sendMessage: async (sessionId: string, content: string) =>
    mapMessage(await request<ApiMessage>(`/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    })),
  setPaused: async (sessionId: string, paused: boolean) =>
    mapSession(await request<ApiSession>(`/sessions/${encodeURIComponent(sessionId)}/${paused ? "pause" : "resume"}`, {
      method: "POST",
    })),
  enablePaper: (sessionId: string) => request(
    `/paper/sessions/${encodeURIComponent(sessionId)}/enable`,
    { method: "POST", body: JSON.stringify({}) },
  ),
  getPaperSession: async (sessionId: string) => mapPaperDetail(
    await request<ApiPaperDetail>(`/paper/sessions/${encodeURIComponent(sessionId)}`),
  ),
};
