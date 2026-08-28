from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeIntent:
    id: str
    description: str
    provider_ids: list[str]
    requires_object_type: str | None = None


# 系统支持的所有知识意图（金融版）
KNOWLEDGE_INTENTS: dict[str, KnowledgeIntent] = {
    # —— 实时业务数据类（需点击对应卡片） ——
    "account_info": KnowledgeIntent(
        id="account_info", description="账户信息咨询（余额、状态、开户信息）",
        provider_ids=["api.account"], requires_object_type="account"),
    "transaction_info": KnowledgeIntent(
        id="transaction_info", description="交易流水/转账记录咨询",
        provider_ids=["api.transaction"], requires_object_type="transaction"),
    "loan_application_info": KnowledgeIntent(
        id="loan_application_info", description="贷款申请进度咨询",
        provider_ids=["api.loan_application"], requires_object_type="loan_application"),
    "ticket_info": KnowledgeIntent(
        id="ticket_info", description="工单进度咨询",
        provider_ids=["api.ticket"], requires_object_type="ticket"),
    # —— 产品咨询类 ——
    "loan_product_info": KnowledgeIntent(
        id="loan_product_info", description="贷款产品咨询（利率、期限、还款方式、准入条件）",
        provider_ids=["api.loan_product", "rag.default"]),
    "wealth_product_info": KnowledgeIntent(
        id="wealth_product_info", description="理财产品咨询（风险等级、收益率、起购金额、开放规则）",
        provider_ids=["api.wealth_product", "rag.default"]),
    "deposit_info": KnowledgeIntent(
        id="deposit_info", description="存款产品与利率咨询",
        provider_ids=["faq.default", "rag.default"]),
    "credit_card_info": KnowledgeIntent(
        id="credit_card_info", description="信用卡咨询（年费、权益、额度、还款规则）",
        provider_ids=["faq.default", "rag.default"]),
    "fund_info": KnowledgeIntent(
        id="fund_info", description="基金产品咨询（类型、净值、风险等级）",
        provider_ids=["rag.default"]),
    # —— 政策与规则类 ——
    "rate_policy": KnowledgeIntent(
        id="rate_policy", description="利率说明咨询", provider_ids=["faq.default", "rag.default"]),
    "fee_policy": KnowledgeIntent(
        id="fee_policy", description="手续费规则咨询", provider_ids=["faq.default", "rag.default"]),
    "prepayment_policy": KnowledgeIntent(
        id="prepayment_policy", description="提前还款政策咨询", provider_ids=["faq.default", "rag.default"]),
    "credit_repayment_policy": KnowledgeIntent(
        id="credit_repayment_policy", description="信用卡还款规则咨询", provider_ids=["faq.default"]),
    "risk_notice": KnowledgeIntent(
        id="risk_notice", description="风险提示咨询", provider_ids=["faq.default", "rag.default"]),
    "guide_info": KnowledgeIntent(
        id="guide_info", description="使用指南与办理流程咨询（开户、手机银行、贷款流程等）",
        provider_ids=["rag.default", "faq.default"]),
    "general_finance_info": KnowledgeIntent(
        id="general_finance_info", description="金融通用信息咨询",
        provider_ids=["faq.default", "rag.default"]),
}
