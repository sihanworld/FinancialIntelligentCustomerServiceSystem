"""Action：银行卡/信用卡挂失"""
import re
import uuid
from datetime import datetime
from typing import Any

from financecs.domain.state import DialogueState
from financecs.infrastructure.finance_client import finance_client
from financecs.task.action.base import Action, ActionResult


class ActionReportCardLoss(Action):
    name = "action_report_card_loss"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        slots = state.active_task.slots if state.active_task is not None else {}
        sender_id = state.sender_id

        card_no = str(slots.get("loss_card_no") or "").strip()
        loss_reason = str(slots.get("loss_reason") or "").strip() or "卡片丢失"
        id_verify = str(slots.get("id_verify_info") or "").strip()

        # 1) 卡号格式校验
        if not re.fullmatch(r"\d{16,19}", card_no):
            return ActionResult(updated_slots={
                "loss_result": "failed",
                "loss_message": "卡号格式不正确，请提供 16-19 位数字卡号。",
            })

        # 2) 身份验证信息基础校验（证件后 6 位或 11 位手机号）
        if not (re.fullmatch(r"\d{6}", id_verify) or re.fullmatch(r"1\d{10}", id_verify)):
            return ActionResult(updated_slots={
                "loss_result": "failed",
                "loss_message": "身份验证信息格式不正确，请提供证件号码后 6 位或银行预留手机号。",
            })

        # 3) 核实卡片归属（卡必须属于当前登录客户）
        check = await finance_client.call(sender_id, "GET", f"/api/v1/cards/{card_no}")
        if not check.ok:
            if check.biz_code in ("CARD_NOT_FOUND", "NOT_FOUND"):
                message = "没有查询到该卡片，请核对卡号后重试。"
            elif check.biz_code in ("CUSTOMER_SCOPE_FORBIDDEN", "FORBIDDEN"):
                message = "该卡片不属于您当前登录的客户，无法为您办理挂失。"
            else:
                message = f"卡片核实失败：{check.message or check.biz_code or '未知原因'}。"
            return ActionResult(updated_slots={"loss_result": "failed", "loss_message": message})

        # 4) 提交挂失（幂等号保证同轮重试不重复挂失）
        request_no = f"CS{uuid.uuid4().hex[:20].upper()}"
        result = await finance_client.call(
            sender_id, "POST", f"/api/v1/cards/{card_no}/loss-report",
            json_body={"request_no": request_no, "loss_reason": loss_reason},
        )
        if not result.ok:
            if result.biz_code in ("CARD_STATUS_FORBIDDEN", "CONFLICT"):
                message = f"该卡片当前状态不允许挂失（可能已挂失或已注销）。{result.message or ''}"
            else:
                message = f"挂失提交失败：{result.message or result.biz_code or '未知原因'}。请稍后重试或转人工。"
            return ActionResult(updated_slots={"loss_result": "failed", "loss_message": message})

        return ActionResult(updated_slots={
            "loss_result": "success",
            "loss_card_tail": card_no[-4:],
            "loss_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "loss_report_no": request_no,
        })
