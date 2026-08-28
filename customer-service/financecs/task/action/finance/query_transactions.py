"""Action：查询账户交易明细"""
from typing import Any

from financecs.domain.state import DialogueState
from financecs.infrastructure.finance_client import finance_client
from financecs.task.action.base import Action, ActionResult
from financecs.task.action.finance.shared import (
    TRANSACTION_TYPE_DESC, first_str, format_dt, looks_like_card_no, parse_query_range,
)


class ActionQueryTransactions(Action):
    name = "action_query_transactions"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        slots = state.active_task.slots if state.active_task is not None else {}
        account_ref = str(slots.get("account_no") or "").strip()

        if not account_ref:
            return ActionResult(updated_slots={
                "transaction_query_success": "false",
                "transaction_query_message": "请先提供您的账户号或银行卡号。",
            })

        sender_id = state.sender_id
        account_no = account_ref
        if looks_like_card_no(account_ref):
            card_result = await finance_client.call(sender_id, "GET", f"/api/v1/cards/{account_ref}")
            if card_result.ok and isinstance(card_result.data, dict):
                account_no = first_str(card_result.data, "account_no") or account_ref
            else:
                return ActionResult(updated_slots={
                    "transaction_query_success": "false",
                    "transaction_query_message": f"没有查询到该卡号对应的账户：{card_result.message or '请核对卡号后重试'}",
                })

        start, end, date_desc = parse_query_range(slots.get("query_date"))
        params = {
            "start_time": format_dt(start),
            "end_time": format_dt(end),
            "page_no": 1,
            "page_size": 10,
        }
        result = await finance_client.call(sender_id, "GET",
                                           f"/api/v1/accounts/{account_no}/transactions", params=params)
        if not result.ok:
            return ActionResult(updated_slots={
                "transaction_query_success": "false",
                "account_no": account_no,
                "transaction_query_message": self._failure_message(result.biz_code, result.message),
            })

        data = result.data if isinstance(result.data, dict) else {}
        rows = data.get("list") or []
        total = data.get("total_count", len(rows))

        return ActionResult(updated_slots={
            "transaction_query_success": "true",
            "account_no": account_no,
            "query_date_desc": date_desc,
            "transaction_count": str(total),
            "transaction_summary": self._build_summary(rows),
        })

    @staticmethod
    def _build_summary(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "该时间段内没有查询到交易记录。"
        lines = []
        for row in rows[:5]:
            tx_time = str(row.get("transaction_at") or "")[:16]
            type_desc = TRANSACTION_TYPE_DESC.get(str(row.get("transaction_type")), str(row.get("transaction_type") or "交易"))
            amount = str(row.get("transaction_amount") or "0.00")
            direction = "+" if str(row.get("transaction_type")) in ("deposit", "loan_disbursement", "wealth_redeem", "wealth_income", "refund") else "-"
            counterparty = row.get("counterparty_name") or row.get("merchant_name") or ""
            line = f"{tx_time} {type_desc} {direction}{amount} 元"
            if counterparty:
                line += f"（{counterparty}）"
            lines.append(line)
        return "；".join(lines) + "。"

    @staticmethod
    def _failure_message(biz_code: str, message: str) -> str:
        if biz_code in ("ACCOUNT_NOT_FOUND", "CARD_NOT_FOUND", "NOT_FOUND"):
            return "没有查询到该账户，请核对账户号或卡号后再试。"
        if biz_code in ("CUSTOMER_SCOPE_FORBIDDEN", "FORBIDDEN"):
            return "该账户不属于您当前登录的客户，请确认您查询的是本人账户。"
        if biz_code == "NETWORK_ERROR":
            return "金融业务系统暂时不可用，请稍后再试。"
        return f"交易查询失败：{message or biz_code or '未知原因'}。"
