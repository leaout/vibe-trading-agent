export type AgentMode = "observe" | "paper" | "approval" | "live";
export type SessionStatus = "running" | "paused" | "draft" | "attention";
export type SignalSide = "BUY" | "SELL" | "HOLD";

export interface AuthUser {
  id: string;
  username: string;
  createdAt: string;
}

export interface TradingSession {
  id: string;
  name: string;
  symbol: string;
  venue: string;
  assetClass: string;
  timeframe: string;
  status: SessionStatus;
  mode: AgentMode;
  pnlPercent: number;
  lastActivity: string;
  promptVersion: number;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  source?: string;
}

export interface ChartSignal {
  id: string;
  timestamp: number;
  price: number;
  side: SignalSide;
  state: "candidate" | "approved" | "rejected" | "filled";
  label: string;
  confidence?: number;
}

export interface DecisionAudit {
  signalId: string;
  sessionId: string;
  context: {
    strategy?: Record<string, unknown>;
    signal?: Record<string, unknown>;
    recent_news?: Array<Record<string, unknown>>;
    model_request?: Record<string, unknown>;
  };
  modelResponse: Record<string, unknown> | null;
  decision: Record<string, unknown> | null;
  execution: Record<string, unknown> | null;
  startedAt: string;
  completedAt: string | null;
  durationMs: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  version?: number;
  status?: "streaming" | "complete" | "failed";
}

export interface StrategyPromptVersion {
  version: number;
  summary: string;
  createdAt: string;
  active: boolean;
  strategy?: Record<string, unknown>;
  warning?: string;
}

export interface AgentEvent {
  id: string;
  timestamp: string;
  type: "signal" | "context" | "model" | "risk" | "order" | "system";
  title: string;
  detail: string;
  state: "success" | "warning" | "neutral" | "error";
  durationMs?: number;
}

export interface SessionSnapshot {
  session: TradingSession;
  candles: Candle[];
  signals: ChartSignal[];
  messages: ChatMessage[];
  promptVersions: StrategyPromptVersion[];
  events: AgentEvent[];
}

export interface PaperAccountDetail {
  account: {
    id: string;
    name: string;
    currency: string;
    initialCash: number;
    cash: number;
    marketValue: number;
    totalEquity: number;
    realizedPnl: number;
    unrealizedPnl: number;
  };
  positions: Array<{
    instrument: string;
    quantity: number;
    availableQuantity: number;
    averageCost: number;
    lastPrice: number;
    marketValue: number;
    unrealizedPnl: number;
  }>;
  orders: Array<{
    id: string;
    signalId: string;
    side: "buy" | "sell";
    instrument: string;
    quantity: number;
    price: number;
    fee: number;
    status: "filled" | "rejected";
    rejectionReason?: string;
    createdAt: string;
  }>;
}

export interface ModelStatus {
  enabled: boolean;
  configured: boolean;
  decisionEnabled: boolean;
  provider: string;
  model: string;
  apiKeyEnv: string;
  minimumConfidence: number;
}

export interface ModelProfile {
  id: string;
  name: string;
  provider: "openai" | "deepseek" | "anthropic" | "openai_compatible";
  model: string;
  baseUrl: string;
  apiKeyEnv: string;
  secretConfigured: boolean;
  timeoutSeconds: number;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  publishedAt: string;
  assetClass: string;
  instrument?: string;
  category: string;
}
