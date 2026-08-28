"""Action：获取客户授信额度（贷款申请前置）"""
from datetime import datetime
from typing import Any

from financecs.domain.state import DialogueState
from financecs.infrastructure.finance_client import finance_client
from financecs.task.action.base import Action, ActionResult


class ActionFetchCreditLimit(Action):
    name = "action_fetch_credit_limit"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        sender_id = state.sender_id
        result = await finance_client.call(sender_id, "GET", f"/api/v1/customers/{sender_id}/credit-limits")

        if not result.ok:
            return ActionResult(updated_slots={
                "credit_limit_found": "false",
                "credit_limit_message": f"授信额度查询失败：{result.message or '请稍后再试'}。",
            })

        data = result.data if isinstance(result.data, dict) else {}
        limits = data.get("list") or []

        # 选取状态可用且未过期的额度
        now = datetime.now()
        usable = None
        for limit in limits:
            available = limit.get("available_limit_amount")
            valid_to = limit.get("valid_to")
            if available in (None, "", "0", "0.00"):
                continue
            if valid_to:
                try:
                    valid_dt = datetime.fromisoformat(str(valid_to).replace(" ", "T"))
                    if valid_dt < now:
                        continue
                except ValueError:
                    pass
            usable = limit
            break

        if usable is None:
            return ActionResult(updated_slots={
                "credit_limit_found": "false",
                "credit_limit_message": "您当前暂无可用的授信额度。贷款申请需要先完成授信评估并获得额度。",
            })

        return ActionResult(updated_slots={
            "credit_limit_found": "true",
            "limit_no": str(usable.get("limit_no") or ""),
            "available_limit_amount": str(usable.get("available_limit_amount") or ""),
        })
