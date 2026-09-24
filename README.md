# Vibe Trading Agent

[English](README_EN.md) | 中文

Vibe Trading Agent 是一个面向 A 股、美股和加密货币的多市场交易 Agent。每个策略都是一个长期会话：用户用自然语言创建和修改策略，系统持续读取行情，在闭合 K 线上生成候选信号，再由大模型结合近期财经资讯复核，最终交给确定性风控和系统模拟账户执行。

> 当前仅支持观察模式和模拟交易，不支持真实自动下单。

## 已实现

- React + TypeScript 工作台：K 线、信号标记、策略聊天、Prompt 版本、决策事件和亮/暗主题。
- FastAPI 服务：登录认证、策略 Session、SSE 实时事件、行情、资讯、模型决策和模拟账户。
- 多市场公开行情：A 股使用 cpptdx/东方财富/新浪，美股使用 Yahoo Finance，加密货币使用 Binance。
- 分钟、小时、日、周、月、年及全部历史周期。
- DeepSeek、OpenAI、Claude 和 OpenAI-compatible 模型。
- 系统 Paper Broker：资金、持仓、委托、成交、费用、仓位限制、信号幂等和 A 股 T+1。
- 财经资讯：A 股东方财富、美股 Yahoo Finance、加密货币 Binance 公告。
- 决策审计：保存信号使用的策略、指标、资讯、模型输入/输出和模拟执行结果；点击 K 线信号查看。

## 决策流程

```text
自然语言策略
  → 受约束的策略版本
  → 闭合 K 线与技术指标
  → 候选 BUY / SELL 信号
  → 大模型结合近期资讯输出 BUY / SELL / HOLD
  → 确定性资金、仓位和 T+1 检查
  → 模拟账户成交或拒绝
```

资讯按 Session 标的订阅、持久化并去重。候选信号出现时，系统默认读取该标的最近 48 小时最多 8 条资讯作为临时上下文。资讯不会写入普通聊天历史，也不会单独触发下单。模型无权决定仓位、绕过风控或调用 Broker；调用失败、超时、低置信度或输出无效时统一降级为 `HOLD`。

## 快速开始

要求：Python 3.10+、Node.js 20+。

```powershell
cd E:\pro\curs-trading-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
Copy-Item .env.v2.example .env
Copy-Item .env.local.example .env.local

cd web_v2
npm install
```

启动后端：

```powershell
cd E:\pro\curs-trading-agent
.\.venv\Scripts\python.exe -m trading_v2
```

启动前端：

```powershell
cd E:\pro\curs-trading-agent\web_v2
npm run dev
```

访问地址：

- Web：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8010/api/v2`
- OpenAPI：`http://127.0.0.1:8010/docs`

首次打开 Web 时创建本地管理员账户。密码使用 PBKDF2 哈希保存，登录状态使用 HttpOnly Cookie。`.env` 和 `.env.local` 均被 Git 忽略；不要强制添加它们，也不要提交 API Key、Broker 密码或 Session 文件。

## 模型配置

将 `.env.local.example` 复制为 `.env.local`，然后只在本机填写密钥：

```dotenv
TRADING_V2_MODEL_ENABLED=true
TRADING_V2_MODEL_PROVIDER=deepseek
TRADING_V2_MODEL_NAME=deepseek-chat
TRADING_V2_MODEL_API_KEY_ENV=DEEPSEEK_API_KEY
DEEPSEEK_API_KEY=your-secret
```

加载优先级为系统环境变量 → `.env.local` → `.env` → 内置默认值。推荐将普通运行参数放在 `.env`，所有密钥只放在 `.env.local`。仓库中的两个 `*.example` 文件只能保留占位符。

其他提供方：

| 提供方 | `TRADING_V2_MODEL_PROVIDER` | Key 环境变量示例 |
|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Claude | `anthropic` | `ANTHROPIC_API_KEY` |
| OpenAI-compatible | `openai_compatible` | 自定义，并设置 `TRADING_V2_MODEL_BASE_URL` |

页面左下角“决策模型”可以检查配置并执行不产生交易的连接测试。

## 数据与资讯

默认使用 `data/trading_v2.db`。生产环境可通过 `TRADING_V2_DATABASE_URL` 使用 PostgreSQL。

公开行情和资讯接口无需 API Key，但可能受到限流、地区限制和历史窗口限制。行情获取失败时，界面会明确显示错误，不会使用测试数据伪装真实行情。资讯默认每 60 秒更新；相关配置见 [.env.v2.example](.env.v2.example)。

示例标的：

- A 股：`cn_equity:XSHG:600519`
- 美股：`us_equity:XNAS:AAPL`
- 加密货币：`crypto:BINANCE:BTCUSDT`

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_trading_v2*.py" -v

cd web_v2
npm run build
```

## 项目结构

```text
trading_v2/  后端、策略 Session、行情、资讯、决策与模拟交易
web_v2/      React 工作台
docs/v2/     架构、数据模型、API 与交易生命周期
test/        V2 自动化测试
```

## 文档

- [架构](docs/v2/ARCHITECTURE.md)
- [交易生命周期](docs/v2/TRADING_LIFECYCLE.md)
- [API](docs/v2/API.md)
- [数据模型](docs/v2/DATA_MODEL.md)
- [English README](README_EN.md)
