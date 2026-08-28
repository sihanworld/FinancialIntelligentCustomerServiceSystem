"""Action：查询账户余额（支持账户号或卡号）"""
from typing import Any

from financecs.domain.state import DialogueState
from financecs.infrastructure.finance_client import finance_client
from financecs.task.action.base import Action, ActionResult
from financecs.task.action.finance.shared import ACCOUNT_STATUS_DESC, first_str, looks_like_card_no


class ActionQueryAccountBalance(Action):
    name = "action_query_account_balance"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        slots = state.active_task.slots if state.active_task is not None else {}
        account_ref = str(slots.get("account_no") or "").strip()

        if not account_ref:
            return ActionResult(updated_slots={
                "account_query_success": "false",
                "account_query_message": "请先提供您的账户号或银行卡号。",
            })

        sender_id = state.sender_id
        account_no = account_ref

        # 卡号 → 账户号 解析（走中台扩展接口）
        if looks_like_card_no(account_ref):
            card_result = await finance_client.call(sender_id, "GET", f"/api/v1/cards/{account_ref}")
            if card_result.ok and isinstance(card_result.data, dict):
                account_no = first_str(card_result.data, "account_no") or account_ref
            else:
                return ActionResult(updated_slots={
                    "account_query_success": "false",
                    "account_query_message": f"没有查询到该卡号对应的账户：{card_result.message or '请核对卡号后重试'}",
                })

        result = await finance_client.call(sender_id, "GET", f"/api/v1/accounts/{account_no}")
        if not result.ok:
            return ActionResult(updated_slots={
                "account_query_success": "false",
                "account_no": account_no,
                "account_query_message": self._failure_message(result.biz_code, result.message),
            })

        data = result.data if isinstance(result.data, dict) else {}
        product = data.get("account_product") or {}
        status_desc = ACCOUNT_STATUS_DESC.get(str(data.get("account_status")), str(data.get("account_status") or "未知"))

        return ActionResult(updated_slots={
            "account_query_success": "true",
            "account_no": account_no,
            "account_status_desc": status_desc,
            "balance_amount": str(data.get("balance_amount") or "0.00"),
            "frozen_amount": str(data.get("frozen_amount") or "0.00"),
            "available_amount": self._available_amount(data),
            "account_product_name": f"账户类型：{product.get('product_name') or product.get('product_code') or '未知'}。" if product else "",
        })

    @staticmethod
    def _available_amount(data: dict[str, Any]) -> str:
        if data.get("available_amount") is not None:
            return str(data.get("available_amount"))
        try:
            balance = float(data.get("balance_amount") or 0)
            frozen = float(data.get("frozen_amount") or 0)
            return f"{balance - frozen:.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @staticmethod
    def _failure_message(biz_code: str, message: str) -> str:
        if biz_code in ("ACCOUNT_NOT_FOUND", "CARD_NOT_FOUND", "NOT_FOUND"):
            return "没有查询到该账户，请核对账户号或卡号后再试。"
        if biz_code in ("CUSTOMER_SCOPE_FORBIDDEN", "FORBIDDEN"):
            return "该账户不属于您当前登录的客户，请确认您查询的是本人账户。"
        if biz_code == "NETWORK_ERROR":
            return "金融业务系统暂时不可用，请稍后再试，或转人工处理。"
        return f"账户查询失败：{message or biz_code or '未知原因'}。您可以核对号码后重试。"
