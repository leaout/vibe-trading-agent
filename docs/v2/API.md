# Vibe Trading V2 API 设计

## 1. 约定

- 基础路径：`/api/v2`。
- JSON 字段使用 `snake_case`，时间使用 ISO 8601 UTC。
- 写操作支持 `Idempotency-Key`，创建订单、审批和发布版本时强制要求。
- 分页使用游标：`?cursor=...&limit=50`。
- 命令成功返回资源或 `202 Accepted + operation_id`；长过程通过 SSE 汇报。
- API Key、Broker 密码和令牌只接受写入，不通过任何读取接口回显。

统一错误：

```json
{
  "error": {
    "code": "STRATEGY_VALIDATION_FAILED",
    "message": "策略包含不支持的指标",
    "details": [{"path": "entry.all[0].field", "reason": "unknown_field"}],
    "request_id": "..."
  }
}
```

## 2. Session 与聊天

### 2.1 本地账户认证

默认开启认证。第一次启动且数据库没有用户时，`POST /auth/register` 允许创建第一个管理员；之后该接口关闭。登录成功后服务端写入 HttpOnly、SameSite=Lax Cookie，客户端不需要接触 token。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/auth/register` | 首次创建本地管理员 |
| `POST` | `/auth/login` | 用户名密码登录 |
| `POST` | `/auth/logout` | 撤销当前 Cookie 会话 |
| `GET` | `/auth/me` | 查询当前登录状态 |

健康检查和 OpenAPI 根路径保持公开；行情、Session、模拟账户和业务 SSE 均需要登录。密码使用 PBKDF2-SHA256 加随机盐存储，服务端不记录明文。

当前已实现 `POST/GET /sessions`、`GET /sessions/{id}`、`POST /messages`、`POST /pause`、`POST /resume`、`POST /evaluate` 和 `GET /events`。表中其余接口为后续契约。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/sessions` | 创建策略对话 Session |
| `GET` | `/sessions` | Session 列表 |
| `GET` | `/sessions/{id}` | 工作区快照 |
| `PATCH` | `/sessions/{id}` | 修改名称等非交易字段 |
| `POST` | `/sessions/{id}/messages` | 发送消息并启动流式回复 |
| `GET` | `/sessions/{id}/messages` | 分页读取对话 |
| `POST` | `/sessions/{id}/pause` | 暂停信号处理 |
| `POST` | `/sessions/{id}/resume` | 恢复信号处理 |
| `POST` | `/sessions/{id}/evaluate` | 立即执行一次闭合 K 线候选信号评估 |
| `GET` | `/sessions/{id}/events` | 当前 Session 的 SSE 实时事件 |
| `POST` | `/sessions/{id}/archive` | 归档，不删除审计数据 |

发送自然语言修改：

```http
POST /api/v2/sessions/9d.../messages
Idempotency-Key: msg-20260921-001
```

```json
{
  "content": "把放量条件从 2 倍改成 1.5 倍，只在上午交易",
  "expected_strategy_version": 7
}
```

当前同步返回助手消息；模型调用超时或校验失败时，消息会说明原因且版本保持草稿：

```json
{
  "id": "...",
  "session_id": "...",
  "role": "assistant",
  "content": "已保存你的修改，但暂未生成可运行策略……",
  "version": 2,
  "status": "complete",
  "created_at": "2026-09-22T08:00:00Z"
}
```

后续异步化后再引入 `operation_id`；`expected_strategy_version` 与幂等键也尚未实现。

## 3. 策略版本

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/sessions/{id}/strategy` | 当前生效版本和最新草稿 |
| `GET` | `/sessions/{id}/strategy/versions` | 版本历史 |
| `GET` | `/strategy-versions/{version_id}` | 获取具体版本 |
| `GET` | `/strategy-versions/{version_id}/diff?against=...` | 结构化差异 |
| `POST` | `/strategy-versions/{version_id}/publish` | 发布草稿 |
| `POST` | `/sessions/{id}/rollback` | 基于历史版本创建并发布新版本 |
| `POST` | `/strategy-versions/{version_id}/validate` | 再次执行 Schema 与语义校验 |

发布请求：

```json
{
  "expected_active_version": 7,
  "effective_policy": "next_closed_bar",
  "reason": "用户确认聊天生成的修改"
}
```

`observe` 和 `paper` 可由用户配置聊天修改自动发布；`approval` 和 `live` 必须显式发布。发布不会修改已经创建的信号或正在运行的 Agent Run。

## 4. 运行控制

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/sessions/{id}/runtime` | 行情、模型、Broker 与运行状态 |
| `PUT` | `/sessions/{id}/mode` | 切换运行模式 |
| `POST` | `/sessions/{id}/start` | 启动 Session Runtime |
| `POST` | `/sessions/{id}/stop` | 有序停止，不撤销已提交订单 |
| `POST` | `/risk/kill-switch/engage` | 全局禁止新增订单 |
| `POST` | `/risk/kill-switch/release` | 解除，要求高权限及原因 |
| `GET` | `/risk/limits` | 当前全局风险限制 |

切换到 `live` 时后端必须检查：账户实盘权限、Broker 健康、行情新鲜度、风险配置、未完成对账和操作者权限。不能仅依赖前端确认框。

## 5. 行情与图表

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/market/instruments/search?q=...` | 搜索标准标的 |
| `GET` | `/market/bars` | 查询 K 线 |
| `GET` | `/market/status` | 当前行情 Provider 健康与延迟 |
| `GET` | `/sessions/{id}/annotations` | 查询信号、决策、风控和成交标注 |

K 线查询示例：

```http
GET /api/v2/market/bars?instrument=CN_EQUITY:XSHG:600000&timeframe=5m&from=...&to=...
```

公开行情示例：`US_EQUITY:XNAS:AAPL`、`CRYPTO:BINANCE:BTCUSDT`。默认 Provider 为 `public`，也可设置 `TRADING_V2_MARKET_DATA_PROVIDER=cpptdx` 强制只使用 cpptdx。

当前返回的每根 Bar 包含 `source` 和 `is_closed`；后续数据路由层会增加 `quality`。图表默认只用闭合 Bar 计算指标，最后一根未闭合 Bar 仅用于视觉展示。

标注响应：

```json
{
  "items": [{
    "id": "...",
    "type": "model_buy",
    "market_time": "2026-09-21T02:30:00Z",
    "price": "12.35",
    "label": "AI 买入 82%",
    "event_id": "...",
    "correlation_id": "..."
  }]
}
```

## 6. 信号、决策与时间线

当前候选信号与模型决策随 `GET /sessions/{id}` 工作区快照的 `signals` 和 `events` 字段返回；独立查询接口是后续契约。模型决策会把图表信号投影为 `approved/rejected` 并在时间线显示置信度和理由。后台只扫描状态为 `running` 且具有合法结构化策略的 Session。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/sessions/{id}/signals` | 候选信号列表 |
| `GET` | `/signals/{id}` | 信号及触发事实 |
| `GET` | `/signals/{id}/decision` | 模型决策与校验结果 |
| `GET` | `/sessions/{id}/timeline` | 聚合后的审计时间线 |
| `GET` | `/events/{event_id}` | 单个审计事件详情 |

面向 UI 的接口返回必要摘要；模型原始响应仅在诊断权限下可见，并在返回前脱敏。

## 7. 审批、订单与持仓

当前已经实现系统内部模拟账户的最小接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/paper/accounts` | 查询系统模拟账户 |
| `POST` | `/paper/accounts` | 创建内部模拟账户 |
| `GET` | `/paper/accounts/{id}` | 账户、持仓、委托与成交快照 |
| `POST` | `/paper/sessions/{id}/enable` | 绑定账户并将 Session 切换为 paper |
| `GET` | `/paper/sessions/{id}` | 查询 Session 绑定的模拟账户 |

当前只模拟市价立即成交。BUY 使用策略 `max_position_pct` 作为该账户该标的的总仓位上限；A 股按 100 股取整并执行 T+1。一个 `signal_id` 最多生成一个模拟委托。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/approvals?status=pending` | 待审批委托 |
| `POST` | `/approvals/{id}/approve` | 批准，随后重新执行时效与风控校验 |
| `POST` | `/approvals/{id}/reject` | 拒绝并记录原因 |
| `GET` | `/orders` | 订单列表 |
| `GET` | `/orders/{id}` | 订单及 Broker 事件 |
| `POST` | `/orders/{id}/cancel` | 请求撤单 |
| `GET` | `/accounts/{id}` | 脱敏账户摘要 |
| `GET` | `/accounts/{id}/positions` | 当前持仓 |

批准请求不直接表示一定下单。系统必须重新检查决策有效期、最新行情、可用资金、持仓和 Kill Switch；失败时返回新的风险拒绝事件。

## 8. 连接与配置

当前已经实现：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/model/status` | 返回提供方、模型名、密钥是否已加载和最低置信度，不返回密钥 |
| `POST` | `/model/test` | 发起一次无交易结构化响应测试，并更新运行状态 |

以下为后续契约：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/connections` | 行情、模型、Broker 配置状态 |
| `POST` | `/connections/{id}/test` | 执行无交易连接测试 |
| `PUT` | `/model-profiles/{id}` | 更新模型配置；密钥为 write-only |
| `GET` | `/model-profiles` | 返回模型名、超时及 `secret_configured` |
| `PUT` | `/market-routing` | 配置各市场 Provider 的主备顺序 |

生产环境优先从环境变量或密钥服务读取凭证。API 不保存或返回明文密钥。

## 8.1 财经资讯

```http
GET /api/v2/news?instrument=us_equity:XNAS:AAPL&limit=20
```

返回统一的 `id/title/summary/url/source/published_at/asset_class/instrument/category`。当前自动路由：A 股东方财富、美股 Yahoo Finance、Crypto Binance 公告。接口会同步写入 `financial_news_v2` 并按来源 ID/URL 去重。后台订阅 Runtime 对运行中策略定时扫描，新文章通过 Session SSE 发送 `event: news`；资讯源故障返回 502，但不改变交易 Runtime 状态。

## 9. SSE 实时事件

```http
GET /api/v2/sessions/{id}/events?after=01J...
Accept: text/event-stream
```

事件信封：

```text
id: 01J...
event: signal
data: {"schema_version":1,"session_id":"...","correlation_id":"...","occurred_at":"...","payload":{...}}
```

首批 UI 事件：

```text
chat.delta / chat.completed
strategy.drafted / strategy.published
market.bar.closed / market.source.changed
signal
decision.created / decision.failed
risk.approved / risk.rejected
approval.requested / approval.resolved
order.updated
system.health.changed
```

客户端断线重连时发送最后收到的事件 ID。服务端先从审计事件补发，再继续实时推送；慢客户端超出缓冲区时断开并要求从游标恢复。

## 10. 健康检查与安全

- `GET /api/v2/health/live`：进程存活。
- `GET /api/v2/health/ready`：V2 Runtime 已启动；接入数据库后还要检查迁移状态。
- `GET /api/v2/status`：当前 Runtime 与组件状态。
- `GET /api/v2/market/status`：当前行情 Provider 健康和延迟。

所有改变交易行为的端点要求认证、角色权限和审计。浏览器使用同源安全 Cookie 与 CSRF 防护；若使用 Bearer Token，则不得保存到 Local Storage。API 日志禁止记录请求中的密钥和完整账户凭证。
