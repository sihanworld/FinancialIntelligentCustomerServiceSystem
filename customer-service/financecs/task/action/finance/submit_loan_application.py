"""Action：提交贷款申请"""
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from financecs.domain.state import DialogueState
from financecs.infrastructure.finance_client import finance_client
from financecs.task.action.base import Action, ActionResult


class ActionSubmitLoanApplication(Action):
    name = "action_submit_loan_application"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        slots = state.active_task.slots if state.active_task is not None else {}
        sender_id = state.sender_id

        # 校验必备槽位
        limit_no = str(slots.get("limit_no") or "").strip()
        if not limit_no:
            return ActionResult(updated_slots={
                "loan_submit_success": "false",
                "loan_submit_message": "缺少可用的授信额度，无法提交贷款申请。",
            })

        try:
            amount = Decimal(str(slots.get("loan_amount") or "").replace(",", ""))
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            return ActionResult(updated_slots={
                "loan_submit_success": "false",
                "loan_submit_message": "贷款金额格式不正确，请提供一个大于 0 的金额。",
            })

        try:
            term_months = int(str(slots.get("loan_term_months") or "").strip())
            if term_months <= 0:
                raise ValueError
        except ValueError:
            return ActionResult(updated_slots={
                "loan_submit_success": "false",
                "loan_submit_message": "贷款期限格式不正确，请提供大于 0 的月份数。",
            })

        request_no = f"CS{uuid.uuid4().hex[:20].upper()}"
        body = {
            "request_no": request_no,
            "customer_no": sender_id,
            "limit_no": limit_no,
            "apply_amount": str(amount),
            "apply_term_months": term_months,
            "repayment_method": "equal_principal_interest",
            "loan_purpose": str(slots.get("loan_purpose") or "consume"),
            "materials": [],
        }

        result = await finance_client.call(sender_id, "POST", "/api/v1/loan/applications", json_body=body)
        if not result.ok:
            return ActionResult(updated_slots={
                "loan_submit_success": "false",
                "loan_submit_message": self._failure_message(result.biz_code, result.message),
            })

        data = result.data if isinstance(result.data, dict) else {}
        application_no = str(data.get("application_no") or "")
        return ActionResult(updated_slots={
            "loan_submit_success": "true" if application_no else "false",
            "application_no": application_no,
            "loan_amount": str(amount),
            "loan_term_months": str(term_months),
            "loan_submit_message": "" if application_no else "贷款申请提交失败：中台未返回申请编号。",
        })

    @staticmethod
    def _failure_message(biz_code: str, message: str) -> str:
        if biz_code == "CREDIT_LIMIT_NOT_ENOUGH":
            return "您的可用授信额度不足，请调低申请金额后重试。"
        if biz_code == "LOAN_TERM_OUT_OF_RANGE":
            return "申请期限不在该贷款产品允许的期限范围内，请调整期限后重试。"
        if biz_code == "CREDIT_LIMIT_STATUS_FORBIDDEN":
            return "您的授信额度当前状态不允许发起贷款申请，请联系人工客服。"
        if biz_code == "NETWORK_ERROR":
            return "金融业务系统暂时不可用，请稍后再试。"
        return f"贷款申请提交失败：{message or biz_code or '未知原因'}。"
