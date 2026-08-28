"""金融业务 Action 共享工具：枚举映射、日期解析、脱敏"""
import re
from datetime import datetime, timedelta
from typing import Any

# —— 枚举映射 ——
TICKET_TYPE_MAP: dict[str, str] = {
    "账户问题": "account_issue",
    "交易问题": "transaction_issue",
    "理财问题": "wealth_issue",
    "贷款问题": "loan_issue",
    "还款问题": "repayment_issue",
    "投诉": "complaint",
    "其他": "other",
}

TRANSACTION_TYPE_DESC: dict[str, str] = {
    "transfer": "转账", "consume": "消费", "deposit": "入金", "withdraw": "出金",
    "loan_disbursement": "贷款放款", "loan_repayment": "贷款还款",
    "wealth_purchase": "理财申购", "wealth_redeem": "理财赎回",
    "wealth_income": "理财收益入账", "refund": "退款", "cancel": "撤销",
    "reversal": "冲正", "adjustment": "调账",
}

ACCOUNT_STATUS_DESC: dict[str, str] = {
    "normal": "正常", "active": "正常", "frozen": "冻结", "restricted": "限制", "closed": "已销户",
}

CARD_STATUS_DESC: dict[str, str] = {
    "active": "正常", "frozen": "冻结", "lost": "已挂失", "expired": "已过期", "cancelled": "已注销",
}

APPLICATION_STATUS_DESC: dict[str, str] = {
    "created": "已创建", "risk_reviewing": "风控审核中", "manual_reviewing": "人工审批中",
    "approved": "审批通过", "rejected": "审批拒绝", "cancelled": "已取消", "expired": "已过期",
}

LOAN_PURPOSE_MAP: dict[str, str] = {
    "装修": "装修", "教育": "教育", "经营": "经营周转", "消费": "日常消费",
    "旅游": "旅游", "医疗": "医疗",
}


def looks_like_card_no(value: str) -> bool:
    """16-19 位纯数字视为卡号"""
    return bool(re.fullmatch(r"\d{16,19}", value.strip()))


def mask_card_no(value: str) -> str:
    value = value.strip()
    if len(value) <= 4:
        return value
    return f"****{value[-4:]}"


def parse_query_range(query_date: str | None) -> tuple[datetime, datetime, str]:
    """
    将自然语言日期解析为 (start_time, end_time, 展示文案)。
    支持：具体日期（2026-08-26 / 2026/8/26 / 8月26日）、近 7 天、近一个月、昨天/今天；缺省近 7 天。
    """
    now = datetime.now()
    text = (query_date or "").strip()

    if not text:
        start = now - timedelta(days=7)
        return start, now, "近 7 天"

    if "昨" in text:
        day = (now - timedelta(days=1)).date()
        start = datetime(day.year, day.month, day.day)
        return start, start + timedelta(days=1) - timedelta(seconds=1), "昨天"

    if "今" in text:
        day = now.date()
        start = datetime(day.year, day.month, day.day)
        return start, now, "今天"

    if "一个月" in text or "30天" in text or "30 天" in text:
        return now - timedelta(days=30), now, "近 30 天"

    if "7天" in text.replace(" ", "") or "一周" in text or "7日" in text.replace(" ", ""):
        return now - timedelta(days=7), now, "近 7 天"

    # 具体日期
    m = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", text)
    if m:
        day = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return day, day + timedelta(days=1) - timedelta(seconds=1), day.strftime("%Y-%m-%d")

    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", text)
    if m:
        year = now.year
        day = datetime(year, int(m.group(1)), int(m.group(2)))
        if day > now:
            day = datetime(year - 1, int(m.group(1)), int(m.group(2)))
        return day, day + timedelta(days=1) - timedelta(seconds=1), day.strftime("%Y-%m-%d")

    # 兜底：近 7 天
    return now - timedelta(days=7), now, "近 7 天"


def format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def first_str(data: Any, *keys: str) -> str:
    """从中台返回结构中按候选键取第一个非空字符串"""
    if not isinstance(data, dict):
        return ""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    return ""
