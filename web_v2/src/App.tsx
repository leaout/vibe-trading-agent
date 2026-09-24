import { useEffect, useRef, useState } from "react";

import { apiClient, ApiError } from "./api/client";
import { SessionEventStream } from "./api/sse";
import { CandlestickChart } from "./components/CandlestickChart";
import { AuthScreen } from "./components/AuthScreen";
import { ChatPanel } from "./components/ChatPanel";
import { EventTimeline } from "./components/EventTimeline";
import { PaperAccountPanel } from "./components/PaperAccountPanel";
import { ModelSettingsPanel } from "./components/ModelSettingsPanel";
import { NewsPanel } from "./components/NewsPanel";
import { DecisionAuditPanel } from "./components/DecisionAuditPanel";
import { SessionSidebar } from "./components/SessionSidebar";
import type { AgentEvent, AuthUser, Candle, ChartSignal, ChatMessage, DecisionAudit, ModelStatus, NewsArticle, PaperAccountDetail, StrategyPromptVersion, TradingSession } from "./types";

const timeframes = ["1m", "5m", "15m", "30m", "1h", "1D", "1W", "1M", "1Y", "全部"];
const marketProviders = [
  ["auto", "自动路由"],
  ["public", "公开行情"],
  ["cpptdx", "cpptdx（A股）"],
] as const;

function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">(() => (
    localStorage.getItem("vibe-theme") === "light" ? "light" : "dark"
  ));
  const [sessions, setSessions] = useState<TradingSession[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [timeframe, setTimeframe] = useState("5m");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [versions, setVersions] = useState<StrategyPromptVersion[]>([]);
  const [signals, setSignals] = useState<ChartSignal[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [paper, setPaper] = useState<PaperAccountDetail | null>(null);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createPrompt, setCreatePrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [chartLayer, setChartLayer] = useState<"signals" | "positions">("signals");
  const [candles, setCandles] = useState<Candle[]>([]);
  const [marketSource, setMarketSource] = useState("");
  const [marketError, setMarketError] = useState("");
  const [marketProvider, setMarketProvider] = useState(() => localStorage.getItem("vibe-market-provider") ?? "auto");
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [showModelSettings, setShowModelSettings] = useState(false);
  const [showNews, setShowNews] = useState(false);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState("");
  const [decisionAudit, setDecisionAudit] = useState<DecisionAudit | null>(null);
  const [showAuditPanel, setShowAuditPanel] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState("");
  const auditRequestId = useRef(0);
  const newsRequestId = useRef(0);
  const selected = sessions.find((session) => session.id === selectedId);
  const lastCandle = candles[candles.length - 1];
  const previous = candles[candles.length - 2];
  const change = previous && lastCandle ? ((lastCandle.close - previous.close) / previous.close) * 100 : 0;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("vibe-theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("vibe-market-provider", marketProvider);
  }, [marketProvider]);

  useEffect(() => {
    apiClient.getAuthStatus()
      .then(setAuthUser)
      .catch(() => setAuthUser(null))
      .finally(() => setAuthLoading(false));
  }, []);
  const displayedSignals = signals.map((signal) => {
    const order = paper?.orders.find((item) => item.signalId === signal.id);
    return order
      ? { ...signal, state: order.status === "filled" ? "filled" as const : "rejected" as const }
      : signal;
  });
  const paperEvents: AgentEvent[] = (paper?.orders ?? []).slice(0, 5).reverse().map((order) => ({
    id: `paper-${order.id}`,
    timestamp: new Date(order.createdAt).toLocaleTimeString("zh-CN", {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    }),
    type: order.status === "filled" ? "order" : "risk",
    title: order.status === "filled" ? "模拟成交" : "模拟风控拒绝",
    detail: order.status === "filled"
      ? `${order.side.toUpperCase()} ${order.quantity} @ ${order.price.toFixed(2)}，费用 ${order.fee.toFixed(2)}`
      : (order.rejectionReason ?? "订单未通过确定性检查"),
    state: order.status === "filled" ? "success" : "warning",
  }));

  const loadSessions = async () => {
    const remoteSessions = await apiClient.getSessions();
    setSessions(remoteSessions);
    setSelectedId((current) => remoteSessions.some((item) => item.id === current)
      ? current
      : (remoteSessions[0]?.id ?? ""));
  };

  const loadModelStatus = async () => {
    setModelStatus(await apiClient.getModelStatus());
  };

  const loadNews = async () => {
    if (!selected) return;
    const requestId = ++newsRequestId.current;
    setNewsLoading(true);
    setNewsError("");
    try {
      const articles = await apiClient.getNews(`${selected.assetClass}:${selected.venue}:${selected.symbol}`);
      if (requestId !== newsRequestId.current) return;
      setNews(articles);
      setNewsError("");
    } catch (reason) {
      if (requestId !== newsRequestId.current) return;
      const detail = reason instanceof ApiError
        && typeof reason.payload === "object" && reason.payload !== null
        && "detail" in reason.payload && typeof reason.payload.detail === "string"
        ? reason.payload.detail
        : "财经资讯源暂时不可用，请稍后重试。";
      setNewsError(detail);
    } finally {
      if (requestId === newsRequestId.current) setNewsLoading(false);
    }
  };

  const openNews = () => {
    setShowNews(true);
    loadNews().catch(() => undefined);
  };

  const openDecisionAudit = async (signalId: string) => {
    if (!selected) return;
    const requestId = ++auditRequestId.current;
    setShowAuditPanel(true);
    setDecisionAudit(null);
    setAuditError("");
    setAuditLoading(true);
    try {
      const audit = await apiClient.getSignalAudit(selected.id, signalId);
      if (requestId === auditRequestId.current) setDecisionAudit(audit);
    } catch {
      if (requestId === auditRequestId.current) setAuditError("该信号的审计快照暂不可用。新产生的信号会保存完整详情。");
    } finally {
      if (requestId === auditRequestId.current) setAuditLoading(false);
    }
  };

  useEffect(() => {
    newsRequestId.current += 1;
    setNews([]);
    setNewsError("");
    setNewsLoading(false);
    setDecisionAudit(null);
    setShowAuditPanel(false);
    auditRequestId.current += 1;
    setAuditError("");
  }, [selectedId]);

  useEffect(() => {
    if (!authUser) return;
    Promise.all([loadSessions(), loadModelStatus()])
      .catch(() => setError("无法连接 V2 API，请确认后端已启动。"))
      .finally(() => setLoading(false));
  }, [authUser]);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      setVersions([]);
      setSignals([]);
      setEvents([]);
      setPaper(null);
      return;
    }
    let cancelled = false;
    apiClient.getSession(selectedId).then((snapshot) => {
      if (cancelled) return;
      setMessages(snapshot.messages);
      setVersions(snapshot.promptVersions);
      setSignals(snapshot.signals);
      setEvents(snapshot.events);
      setTimeframe(snapshot.session.timeframe);
    }).catch(() => {
      if (!cancelled) setError("会话详情加载失败，请刷新后重试。");
    });
    apiClient.getPaperSession(selectedId).then(setPaper).catch(() => setPaper(null));
    return () => { cancelled = true; };
  }, [selectedId]);

  useEffect(() => {
    if (!selected || !selected.venue || !selected.symbol) {
      setCandles([]);
      setMarketSource("");
      setMarketError("");
      return;
    }
    let cancelled = false;
    const refreshBars = () => apiClient.getMarketBars(
        `${selected.assetClass}:${selected.venue}:${selected.symbol}`,
        timeframe,
        120,
        marketProvider,
      ).then((bars) => {
        if (!cancelled && bars.length >= 1) {
          setCandles(bars);
          setMarketSource(bars[bars.length - 1].source ?? "public");
          setMarketError("");
        }
      }).catch((reason: unknown) => {
        if (!cancelled) {
          setCandles([]);
          setMarketSource("");
          setMarketError(reason instanceof Error ? reason.message : "公开行情暂不可用");
        }
      });
    refreshBars();
    const refreshTimer = window.setInterval(refreshBars, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(refreshTimer);
    };
  }, [selected, timeframe, marketProvider]);

  useEffect(() => {
    if (!selectedId || import.meta.env.VITE_ENABLE_SSE === "false") return undefined;
    const stream = new SessionEventStream();
    stream.connect(selectedId);
    const unsubscribe = stream.subscribe((event) => {
      loadSessions().catch(() => undefined);
      apiClient.getSession(selectedId).then((snapshot) => {
        setMessages(snapshot.messages);
        setVersions(snapshot.promptVersions);
        setSignals(snapshot.signals);
        setEvents(snapshot.events);
      }).catch(() => undefined);
      apiClient.getPaperSession(selectedId).then(setPaper).catch(() => setPaper(null));
      if (event.event === "news" && showNews) loadNews().catch(() => undefined);
    });
    return () => {
      unsubscribe();
      stream.close();
    };
  }, [selectedId, showNews]);

  const createSession = async () => {
    const prompt = createPrompt.trim();
    if (!prompt || creating) return;
    setCreating(true);
    setError("");
    try {
      const session = await apiClient.createSession(prompt);
      setSessions((items) => [session, ...items]);
      setSelectedId(session.id);
      setCreatePrompt("");
      setShowCreate(false);
    } catch {
      setError("创建策略失败，请检查 API 与模型配置。");
    } finally {
      setCreating(false);
    }
  };

  const togglePause = async () => {
    if (!selected) return;
    try {
      const updated = await apiClient.setPaused(selected.id, selected.status === "running");
      setSessions((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch {
      setError("策略状态更新失败。");
    }
  };

  const enablePaper = async () => {
    if (!selected) return;
    try {
      await apiClient.enablePaper(selected.id);
      await loadSessions();
      setPaper(await apiClient.getPaperSession(selected.id));
    } catch {
      setError("模拟账户启用失败，请确认后端已启动。");
    }
  };

  const logout = async () => {
    await apiClient.logout().catch(() => undefined);
    setAuthUser(null);
    setSelectedId("");
  };

  if (authLoading) return <main className="auth-screen"><div className="auth-card"><p>正在检查登录状态…</p></div></main>;
  if (!authUser) return <AuthScreen onAuthenticated={setAuthUser} />;

  const sendMessage = async (content: string) => {
    if (!selected) return;
    const optimistic: ChatMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }),
      status: "complete",
    };
    setMessages((items) => [...items, optimistic]);
    setSending(true);
    setError("");
    try {
      await apiClient.sendMessage(selected.id, content);
      const snapshot = await apiClient.getSession(selected.id);
      setMessages(snapshot.messages);
      setVersions(snapshot.promptVersions);
      setSignals(snapshot.signals);
      setEvents(snapshot.events);
      setSessions((items) => items.map((item) => item.id === selected.id ? snapshot.session : item));
    } catch {
      setMessages((items) => [...items, {
        id: `local-error-${Date.now()}`,
        role: "system",
        content: "消息保存失败，请检查后端服务后重试。",
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }),
        status: "failed",
      }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><span /></div>
          <div><strong>VIBE</strong><em>TRADING</em></div>
        </div>
        <div className="session-title">
          <div className="breadcrumb"><span>策略会话</span>{selected && <><i>/</i><span>{selected.name}</span></>}</div>
          <h1>{selected?.name ?? "创建你的第一个交易策略"}</h1>
          {selected && <div className="session-tags">
            <span className="tag mode">{selected.mode === "paper" ? "模拟交易" : "观察模式"}</span>
            <span className={`tag ${selected.status}`}><i />{selected.status === "paused" ? "已暂停" : selected.status === "draft" ? "草稿" : "运行中"}</span>
          </div>}
        </div>
        <div className="top-actions">
          <div className="portfolio-summary">
            <span>交易权限<strong>{selected?.mode === "paper" ? "模拟交易" : "仅观察"}</strong></span>
            <span>Broker<strong>{paper ? "SYSTEM PAPER" : "未启用"}</strong></span>
          </div>
          {selected && selected.mode !== "paper" && <button className="paper-enable-button" onClick={enablePaper}>启用模拟盘</button>}
          <button className="theme-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="切换主题">{theme === "dark" ? "☼" : "☾"}</button>
          <button className="user-button" onClick={logout} title="退出登录">{authUser.username}</button>
          {selected && <button className={`pause-button ${selected.status !== "running" ? "resume" : ""}`} onClick={togglePause}>
            {selected.status === "draft" ? "▶ 启动策略" : selected.status === "paused" ? "▶ 继续运行" : "Ⅱ 暂停策略"}
          </button>}
        </div>
      </header>

      <main className="workspace">
        <SessionSidebar
          sessions={sessions}
          selectedId={selectedId}
          marketSource={marketSource}
          onCreate={() => setShowCreate(true)}
          onSelect={setSelectedId}
          modelStatus={modelStatus}
          onModelSettings={() => setShowModelSettings(true)}
        />

        {!selected ? (
          <section className="empty-workspace">
            <div className="empty-orbit"><span>V</span></div>
            <p className="eyebrow">CONVERSATION-FIRST TRADING</p>
            <h2>{loading ? "正在加载策略会话…" : "用一句话描述你的交易想法"}</h2>
            <p>Agent 会把自然语言编译成受约束的策略结构，并保存每次修改的完整版本。</p>
            <button onClick={() => setShowCreate(true)}>＋ 创建策略会话</button>
            {error && <small>{error}</small>}
          </section>
        ) : <>
          <div className="market-workspace">
            <section className="market-panel panel-edge">
              <div className="market-toolbar">
                <div className="instrument">
                  <div className="instrument-symbol"><strong>{selected.symbol}</strong><span>{selected.venue}</span></div>
                  <div><h2>{selected.name}</h2><small className={marketError ? "market-error" : ""}>{marketSource ? `${marketSource} 公开行情 · ${timeframe}` : (marketError || "等待公开行情")}</small></div>
                </div>
                <div className="quote">
                  <strong>{lastCandle ? lastCandle.close.toFixed(2) : "—"}</strong>
                  <span className={change >= 0 ? "positive" : "negative"}>{lastCandle ? `${change >= 0 ? "+" : ""}${change.toFixed(2)}%` : "暂无变化"}</span>
                </div>
                <div className="ohlc">
                  <span>开 <b>{lastCandle ? lastCandle.open.toFixed(2) : "—"}</b></span>
                  <span>高 <b className="positive">{lastCandle ? lastCandle.high.toFixed(2) : "—"}</b></span>
                  <span>低 <b className="negative">{lastCandle ? lastCandle.low.toFixed(2) : "—"}</b></span>
                  <span>量 <b>{lastCandle ? lastCandle.volume.toFixed(0) : "—"}</b></span>
                </div>
                <div className="timeframe-switch">
                  {timeframes.map((item) => (
                    <button className={timeframe === item ? "active" : ""} key={item} onClick={() => setTimeframe(item)}>{item}</button>
                  ))}
                </div>
                <select className="market-provider-select" value={marketProvider} onChange={(event) => setMarketProvider(event.target.value)} aria-label="选择行情源">
                  {marketProviders.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <button className="news-button" onClick={openNews}>财经资讯</button>
              </div>

              <div className="chart-legend">
                <span><i className="legend-line ma5" />MA5</span>
                <span><i className="legend-line ma20" />MA20</span>
                <div className="chart-layer-switch">
                  <button className={chartLayer === "signals" ? "active" : ""} onClick={() => setChartLayer("signals")}><i className="signal-dot" />交易信号</button>
                  <button className={chartLayer === "positions" ? "active" : ""} onClick={() => setChartLayer("positions")}>持仓成本</button>
                </div>
              </div>
              <div className="chart-stage">
              <CandlestickChart candles={candles} signals={chartLayer === "signals" ? displayedSignals : []} onSignalClick={openDecisionAudit} />
              </div>

              <div className="chart-stats">
                <span><small>当前仓位</small><strong>{paper ? `${paper.positions.length} 个标的` : "未启用"}</strong></span>
                <span><small>持仓成本</small><strong>{paper?.positions[0] ? paper.positions[0].averageCost.toFixed(2) : "—"}</strong></span>
                <span><small>浮动盈亏</small><strong className={(paper?.account.unrealizedPnl ?? 0) >= 0 ? "positive" : "negative"}>{paper ? paper.account.unrealizedPnl.toFixed(2) : "—"}</strong></span>
                <span><small>策略版本</small><strong>v{selected.promptVersion}</strong></span>
                <span><small>执行权限</small><strong>{selected.mode === "paper" ? "模拟盘" : "仅观察"}</strong></span>
              </div>
              {paper && <PaperAccountPanel detail={paper} />}
            </section>
            <EventTimeline events={[...events, ...paperEvents].slice(-10)} />
          </div>

          <ChatPanel messages={messages} versions={versions} busy={sending} onSend={sendMessage} />
        </>}
      </main>

      {showCreate && <div className="create-backdrop" onMouseDown={() => !creating && setShowCreate(false)}>
        <section className="create-dialog" onMouseDown={(event) => event.stopPropagation()}>
          <p className="eyebrow">NEW TRADING SESSION</p>
          <h2>一句话创建策略</h2>
          <p>包含交易品种、周期、触发条件和风险约束会得到更准确的结果。</p>
          <textarea
            autoFocus
            value={createPrompt}
            onChange={(event) => setCreatePrompt(event.target.value)}
            placeholder="例如：为 600519 创建 5 分钟放量突破策略，单次最大仓位 5%，止损 3%"
            rows={5}
          />
          <div className="create-actions">
            <button className="cancel" onClick={() => setShowCreate(false)} disabled={creating}>取消</button>
            <button onClick={createSession} disabled={!createPrompt.trim() || creating}>{creating ? "正在编译…" : "创建草稿"}</button>
          </div>
        </section>
      </div>}
      {showModelSettings && (
        <ModelSettingsPanel
          status={modelStatus}
          onClose={() => setShowModelSettings(false)}
          onRefresh={loadModelStatus}
        />
      )}
      {showNews && selected && (
        <NewsPanel
          articles={news}
          loading={newsLoading}
          error={newsError}
          instrument={`${selected.symbol}.${selected.venue}`}
          onClose={() => setShowNews(false)}
          onRefresh={() => { loadNews().catch(() => undefined); }}
        />
      )}
      {showAuditPanel && (
        <DecisionAuditPanel
          audit={decisionAudit}
          loading={auditLoading}
          error={auditError}
          onClose={() => { auditRequestId.current += 1; setShowAuditPanel(false); setDecisionAudit(null); setAuditError(""); }}
        />
      )}
    </div>
  );
}

export default App;
