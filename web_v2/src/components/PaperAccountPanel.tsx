import type { PaperAccountDetail } from "../types";

interface Props { detail: PaperAccountDetail; }

const money = (value: number) => value.toLocaleString("zh-CN", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

export function PaperAccountPanel({ detail }: Props) {
  const pnl = detail.account.realizedPnl + detail.account.unrealizedPnl;
  return <section className="paper-account-bar">
    <div className="paper-account-name"><small>PAPER BROKER</small><strong>{detail.account.name}</strong></div>
    <span><small>总资产</small><strong>{money(detail.account.totalEquity)}</strong></span>
    <span><small>可用资金</small><strong>{money(detail.account.cash)}</strong></span>
    <span><small>持仓市值</small><strong>{money(detail.account.marketValue)}</strong></span>
    <span><small>累计盈亏</small><strong className={pnl >= 0 ? "positive" : "negative"}>{pnl >= 0 ? "+" : ""}{money(pnl)}</strong></span>
    <div className="paper-latest-order">
      <small>最近委托</small>
      {detail.orders[0]
        ? <strong className={detail.orders[0].status === "filled" ? "positive" : "negative"}>
            {detail.orders[0].side.toUpperCase()} {detail.orders[0].quantity} @ {detail.orders[0].price.toFixed(2)} · {detail.orders[0].status === "filled" ? "已成交" : "已拒绝"}
          </strong>
        : <strong>等待候选信号</strong>}
    </div>
  </section>;
}
