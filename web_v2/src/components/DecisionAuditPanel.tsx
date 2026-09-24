import type { DecisionAudit } from "../types";

interface DecisionAuditPanelProps {
  audit: DecisionAudit | null;
  loading: boolean;
  error: string;
  onClose: () => void;
}

const pretty = (value: unknown) => JSON.stringify(value ?? {}, null, 2);

export function DecisionAuditPanel({ audit, loading, error, onClose }: DecisionAuditPanelProps) {
  const signal = audit?.context.signal ?? {};
  const indicators = (signal.indicators as Record<string, unknown> | undefined) ?? {};
  const articles = audit?.context.recent_news ?? [];
  const decision = audit?.decision ?? audit?.modelResponse ?? {};
  const execution = audit?.execution;
  const order = execution?.order as Record<string, unknown> | null | undefined;

  return (
    <div className="audit-backdrop" onMouseDown={onClose}>
      <section className="audit-drawer" onMouseDown={(event) => event.stopPropagation()}>
        <header className="audit-heading">
          <div><p className="eyebrow">DECISION AUDIT</p><h2>信号决策详情</h2></div>
          <button onClick={onClose} aria-label="关闭决策详情">×</button>
        </header>
        {loading && <p className="audit-state">正在读取决策快照…</p>}
        {error && <p className="audit-state audit-error">{error}</p>}
        {audit && <div className="audit-content">
          <section className="audit-summary">
            <span>候选方向<strong>{String(signal.side ?? "—").toUpperCase()}</strong></span>
            <span>模型结论<strong>{String(decision.action ?? "待评估").toUpperCase()}</strong></span>
            <span>耗时<strong>{audit.durationMs == null ? "—" : `${audit.durationMs} ms`}</strong></span>
          </section>
          <section className="audit-section">
            <h3>触发信号</h3>
            <p>{String(signal.reason ?? "闭合 K 线满足策略规则")}</p>
            <pre>{pretty(indicators)}</pre>
          </section>
          <section className="audit-section">
            <h3>模型决策</h3>
            <p>{String(decision.rationale ?? "暂无模型说明")}</p>
            <p className="audit-muted">置信度：{typeof decision.confidence === "number" ? `${Math.round(decision.confidence * 100)}%` : "—"} · 状态：{String(decision.status ?? "—")}</p>
            {typeof decision.error === "string" && <p className="audit-error">{decision.error}</p>}
          </section>
          <section className="audit-section">
            <h3>决策时参考资讯（{articles.length}）</h3>
            {!articles.length && <p className="audit-muted">本次没有附带资讯。</p>}
            {articles.map((article, index) => <article className="audit-article" key={String(article.id ?? index)}>
              <strong>{String(article.title ?? "未命名资讯")}</strong>
              <p>{String(article.summary ?? "")}</p>
              <small>{String(article.source ?? "")} · {String(article.published_at ?? "")}</small>
            </article>)}
          </section>
          <section className="audit-section">
            <h3>模拟执行</h3>
            <p>结果：{String(execution?.outcome ?? "处理中")}</p>
            {order && <pre>{pretty(order)}</pre>}
          </section>
          <details className="audit-section audit-raw">
            <summary>查看策略和模型输入快照</summary>
            <pre>{pretty({ strategy: audit.context.strategy, model_request: audit.context.model_request, model_response: audit.modelResponse })}</pre>
          </details>
        </div>}
      </section>
    </div>
  );
}
