-- =====================================================================
-- 客服库 customer_service 建表脚本（表结构部分；库的创建由 scripts/init_cs_db.py 完成）
-- 字符集 utf8mb4 / 存储引擎 InnoDB；连接参数以 .env 的 CS_DATABASE_URL 为准
-- =====================================================================

-- 1) 对话状态表（重建自原 dialogue_states：新增客户号绑定、乐观锁、时间戳）
CREATE TABLE IF NOT EXISTS cs_dialogue_state (
    sender_id       VARCHAR(64)  NOT NULL COMMENT '会话用户标识 = 金融客户号 customer_no',
    customer_no     VARCHAR(64)  NOT NULL COMMENT '金融客户号（与 sender_id 同值，显式冗余便于审计）',
    state_json      LONGTEXT     NOT NULL COMMENT 'DialogueState 全量 JSON（任务栈/会话/轮次/卡片）',
    state_version   BIGINT       NOT NULL DEFAULT 0 COMMENT '乐观锁版本号，每次保存 +1',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (sender_id),
    KEY idx_cds_customer_no (customer_no)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '对话状态持久化表';

-- 2) 消息流水表（历史消息查询、审计回溯）
CREATE TABLE IF NOT EXISTS cs_chat_message (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    sender_id       VARCHAR(64)  NOT NULL COMMENT '客户号',
    session_id      VARCHAR(64)  NOT NULL COMMENT '会话 ID',
    turn_id         VARCHAR(64)  NOT NULL COMMENT '轮次 ID',
    message_id      VARCHAR(64)  NOT NULL COMMENT '消息 ID',
    role            VARCHAR(16)  NOT NULL COMMENT 'user / bot',
    msg_type        VARCHAR(16)  NOT NULL DEFAULT 'text' COMMENT 'text / object',
    text            TEXT         NULL COMMENT '文本内容',
    object_json     TEXT         NULL COMMENT '业务对象卡片 JSON（id/title/type/attributes）',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_message_id (message_id),
    KEY idx_ccm_sender_session (sender_id, session_id, id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '聊天消息流水表';

-- 3) 轮次追踪表（可观测性：意图识别/规划/澄清/耗时全记录）
CREATE TABLE IF NOT EXISTS cs_turn_trace (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    sender_id       VARCHAR(64)  NOT NULL,
    session_id      VARCHAR(64)  NULL,
    message_id      VARCHAR(64)  NOT NULL COMMENT '触发轮次的用户消息 ID',
    request_id      VARCHAR(64)  NULL COMMENT '链路追踪号',
    tracks          VARCHAR(64)  NULL COMMENT '命中轨道：task,knowledge,chitchat',
    plan_json       TEXT         NULL COMMENT 'TurnPlan 原始输出',
    clarify_reason  VARCHAR(64)  NULL COMMENT '澄清原因（ClarifyReason 枚举）',
    flow_id         VARCHAR(64)  NULL COMMENT '轮次结束时的激活流程',
    step_id         VARCHAR(64)  NULL COMMENT '轮次结束时的流程步骤',
    status          VARCHAR(16)  NOT NULL DEFAULT 'ok' COMMENT 'ok / error / degraded',
    error_message   VARCHAR(512) NULL,
    cost_ms         INT          NULL COMMENT '本轮总耗时',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_ctt_sender (sender_id, id),
    KEY idx_ctt_message (message_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '对话轮次追踪表（可观测性）';

-- 4) 工具调用审计表（Action 调中台的入参出参全留痕）
CREATE TABLE IF NOT EXISTS cs_action_audit (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    sender_id       VARCHAR(64)  NOT NULL,
    session_id      VARCHAR(64)  NULL,
    action_name     VARCHAR(64)  NOT NULL COMMENT 'Action 名',
    method          VARCHAR(8)   NULL COMMENT 'GET / POST / ...',
    url             VARCHAR(256) NULL COMMENT '中台请求路径',
    request_json    TEXT         NULL COMMENT '请求体（脱敏后）',
    response_json   TEXT         NULL COMMENT '响应体（截断至 8KB）',
    http_status     INT          NULL,
    biz_code        VARCHAR(64)  NULL COMMENT '中台响应 code（0 或错误码）',
    cost_ms         INT          NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_caa_sender (sender_id, id),
    KEY idx_caa_action (action_name, created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'Action 调用审计表';

-- 5) FAQ 表（知识轨 faq.default 的数据源）
CREATE TABLE IF NOT EXISTS cs_faq (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    category        VARCHAR(64)  NOT NULL COMMENT '分类：rate/fee/repayment/credit_card/risk/account/guide/other',
    question        VARCHAR(256) NOT NULL COMMENT '标准问',
    answer          TEXT         NOT NULL COMMENT '标准答',
    keywords        VARCHAR(512) NULL COMMENT '检索关键词，逗号分隔',
    sort_no         INT          NOT NULL DEFAULT 1,
    status          VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT 'active / disabled',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_faq_category (category, status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'FAQ 知识表';

-- 6) 知识库文档表（知识轨 rag.default 的数据源；预留向量字段）
CREATE TABLE IF NOT EXISTS cs_knowledge_doc (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    category        VARCHAR(64)  NOT NULL COMMENT '分类：product/guide/policy/faq_ext',
    title           VARCHAR(256) NOT NULL,
    content         MEDIUMTEXT   NOT NULL,
    keywords        VARCHAR(512) NULL,
    embedding_json  TEXT         NULL COMMENT '预留：向量嵌入',
    status          VARCHAR(16)  NOT NULL DEFAULT 'active',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_kd_category (category, status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '知识库文档表';
