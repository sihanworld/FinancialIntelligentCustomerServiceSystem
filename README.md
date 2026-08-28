# 金融智能客服系统（FinancialIntelligentCustomerServiceSystem）

由电商智能客服项目（sz0331）改造而来的 **金融智能客服系统**。对话内核（三轨规划 + YAML 流程引擎 + 对话状态持久化）复用，业务边界（YAML 流程 / Action / 知识意图 / 提示词 / 数据库表 / 前端）全部按金融场景重写。

## 目录结构

```
FinancialIntelligentCustomerServiceSystem/
├── finance-data/          # 金融业务数据服务（中台，:8000）——92 张业务表 + 9 组业务 API
│   ├── app/routers/cards.py        # 扩展：卡查询 / 挂失接口
│   ├── sql/finance.sql             # 业务库建表脚本（92 表）
│   ├── sql/ext/001_channel_ai_cs.sql  # 扩展：AI_CS 智能客服渠道
│   ├── init_db.py                  # 建库建表
│   ├── generate/                   # 样本数据生成器（九层）
│   └── .env                        # 远程 MySQL 连接参数（以此为准）
├── customer-service/      # 客服后端（:18082）——FastAPI + LangChain + YAML 流程引擎
│   ├── flow_config/                # 金融版 YAML：system_flows.yml + user_flows.yml（7 个业务流程）
│   ├── sql/customer_service.sql    # 客服库 6 张表（重建）
│   ├── seeds/                      # FAQ / 知识库种子
│   ├── scripts/                    # init_cs_db.py / import_seeds.py
│   ├── financecs/                  # 主包（原 atguigu）
│   │   ├── task/action/finance/    # 金融 Action（余额/交易/贷款/挂失/工单）
│   │   ├── knowledge/              # 金融知识意图 + Provider
│   │   ├── prompt/jinja2/          # 金融版提示词
│   │   └── infrastructure/finance_client.py  # 中台统一客户端
│   └── .env                        # LLM / 中台地址 / 客服库连接（以此为准）
└── frontend/              # 前端（:5174）——Vue3 + Vite，深蓝/白日系简约风格
```

## 快速启动

```bash
# ① 金融业务库（首次）
cd finance-data
uv sync
uv run init_db.py
uv run -m generate.main --profile smoke     # 样本数据；正式演示可用 --profile full
# 应用扩展：AI_CS 渠道（任意 MySQL 客户端执行）
#   source sql/ext/001_channel_ai_cs.sql

# ② 启动金融中台（:8000）
uv run -m app.main

# ③ 客服库（首次）
cd ../customer-service
uv sync
uv run scripts/init_cs_db.py
uv run scripts/import_seeds.py

# ④ 启动客服后端（:18082）
uv run main.py

# ⑤ 前端
cd ../frontend
npm install
npm run dev        # http://127.0.0.1:5174
```

## 配置说明

所有数据库地址 / 端口 / 账号 / 密码均在各服务的 `.env` 中，代码零硬编码：

| 服务 | 配置 | 说明 |
|---|---|---|
| finance-data | `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` | 远程 MySQL，库 `finance`（92 表 + 扩展渠道） |
| customer-service | `CS_DATABASE_URL` | 客服库 `customer_service`（6 张表，远程同实例） |
| customer-service | `FINANCE_API_BASE_URL` | 金融中台地址，默认 `http://127.0.0.1:8000` |
| customer-service | `LLM_*` | LLM 网关（qwen-plus，OpenAI 兼容） |

## 核心能力

- **任务型对话（7 个业务流程）**：欢迎引导 / 账户余额查询 / 交易明细查询 / 贷款申请 / 信用卡挂失 / 投诉工单 / 人工客服；支持流程切换、恢复、取消
- **知识咨询**：贷款、理财、存款、信用卡、基金产品咨询 + 利率/手续费/提前还款/风险提示等 FAQ + 知识库
- **对话管控**：槽位主动追问、业务卡片点击自动填槽、多意图澄清、会话状态持久化与恢复
- **接口**：`/api/chat`（非流式）、`/api/chat/stream`（SSE）、`/api/chat/history`、`/api/sessions`、`/api/sessions/state`、`/health`
- **可观测性**：`cs_turn_trace`（轮次追踪）、`cs_action_audit`（中台调用审计）

## 演示客户号（已验证）

前端 `src/App.vue` 已预置以下演示客户（smoke 样本数据中状态正常、有账户/卡/交易/授信额度的个人客户）：

| 客户号 | 说明 |
|---|---|
| `CUS00000146` | 2 账户 / 2 卡 / 18 笔交易 / 有可用授信额度 |
| `CUS00000076` | 2 账户 / 2 卡 / 18 笔交易 / 有可用授信额度 |
| `CUS00000206` | 账户 ACC0000001378 / 18 笔交易 / 有可用授信额度 |

> 注：样本数据生成器使用的客户状态枚举为 `normal`（正常）。如需更换演示客户，可执行：
> `SELECT customer_no FROM customer WHERE customer_status='normal' AND customer_type='personal' LIMIT 10;`

## 冒烟测试记录（2026-08-27，均已通过）

| 场景 | 结果 |
|---|---|
| 欢迎引导（`/api/sessions`） | 正常返回开场白 |
| 账户余额查询（账户号 → 实时余额） | 返回余额/可用/冻结（finance 库实时数据） |
| 交易明细查询（日期解析 + 流水检索） | 正常返回 |
| 贷款申请（类型/金额/期限/用途 → 授信额度校验 → 提交） | 返回真实申请编号（LAP…） |
| 信用卡挂失（卡号/原因/身份验证 → 挂失落库） | `bank_card.card_status` 变为 `lost` |
| 投诉工单（类型/关联号/描述 → 创建） | 返回真实工单编号（TKT…） |
| 知识咨询（FAQ / 理财产品实时数据） | 答案基于实时数据且含合规风险提示 |
| SSE 流式响应（`/api/chat/stream`） | `message_start → delta → message_end → done` 事件正常 |
| 流程中断与恢复（贷款中插入查余额再恢复） | 挂起/恢复语义正确，槽位保留 |
| 会话状态查询（`/api/sessions/state`） | 激活流程/步骤/槽位正确 |
| 中台调用审计（`cs_action_audit`） | 调用留痕正常 |

详细设计见《金融智能客服系统 · 项目改造与迁移说明文档》。
