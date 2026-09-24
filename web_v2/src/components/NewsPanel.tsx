import type { NewsArticle } from "../types";

interface NewsPanelProps {
  articles: NewsArticle[];
  loading: boolean;
  error: string;
  instrument: string;
  onClose: () => void;
  onRefresh: () => void;
}

export function NewsPanel({ articles, loading, error, instrument, onClose, onRefresh }: NewsPanelProps) {
  return (
    <div className="news-backdrop" onMouseDown={onClose}>
      <aside className="news-drawer" onMouseDown={(event) => event.stopPropagation()}>
        <header className="news-heading">
          <div><p className="eyebrow">MARKET INTELLIGENCE</p><h2>财经资讯</h2><small>{instrument}</small></div>
          <div><button onClick={onRefresh} disabled={loading}>↻</button><button onClick={onClose}>×</button></div>
        </header>
        <p className="news-boundary">资讯仅供研究和决策上下文展示，默认不会直接触发交易。</p>
        <div className="news-list">
          {loading && !articles.length && <p className="news-empty">正在获取最新资讯…</p>}
          {error && <p className="news-error">{error}</p>}
          {!loading && !error && !articles.length && <p className="news-empty">当前来源没有返回资讯。</p>}
          {articles.map((article) => (
            <a href={article.url} target="_blank" rel="noreferrer" className="news-card" key={article.id}>
              <div className="news-meta"><span>{article.source}</span><i>{article.category}</i><time>{new Date(article.publishedAt).toLocaleString("zh-CN", { hour12: false })}</time></div>
              <h3>{article.title}</h3>
              {article.summary && <p>{article.summary}</p>}
            </a>
          ))}
        </div>
      </aside>
    </div>
  );
}
