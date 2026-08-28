"""Action：创建投诉/问题工单"""
import uuid
from typing import Any

from financecs.domain.state import DialogueState
from financecs.infrastructure.finance_client import finance_client
from financecs.task.action.base import Action, ActionResult
from financecs.task.action.finance.shared import TICKET_TYPE_MAP


class ActionCreateTicket(Action):
    name = "action_create_ticket"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        slots = state.active_task.slots if state.active_task is not None else {}
        sender_id = state.sender_id

        # 工单类型：中文 → 枚举；无法识别时兜底 other
        ticket_type_cn = str(slots.get("ticket_type") or "").strip()
        ticket_type = TICKET_TYPE_MAP.get(ticket_type_cn)
        if ticket_type is None:
            for cn, code in TICKET_TYPE_MAP.items():
                if cn in ticket_type_cn:
                    ticket_type = code
                    break
        if ticket_type is None:
            ticket_type = "complaint" if "投诉" in ticket_type_cn else "other"

        related_no = str(slots.get("related_business_no") or "").strip()
        description = str(slots.get("problem_description") or "").strip()
        if not description:
            return ActionResult(updated_slots={
                "ticket_create_success": "false",
                "ticket_message": "请先描述您遇到的问题，再为您创建工单。",
            })

        # 关联编号：无法解析出内部 ID 时，统一并入工单正文（避免中台多态引用校验失败）
        content = description
        if related_no and related_no not in ("无", "没有", "暂无", "none", "-"):
            content = f"关联业务编号：{related_no}。{description}"

        title = description[:32] + ("…" if len(description) > 32 else "")

        request_no = f"CS{uuid.uuid4().hex[:20].upper()}"
        body = {
            "request_no": request_no,
            "customer_no": sender_id,
            "ticket_type": ticket_type,
            "ticket_title": title,
            "ticket_content": content,
            "related_type": "none",
        }

        result = await finance_client.call(sender_id, "POST", "/api/v1/support/tickets", json_body=body)
        if not result.ok:
            if result.biz_code == "NETWORK_ERROR":
                message = "金融业务系统暂时不可用，工单未能创建，请稍后重试。"
            else:
                message = f"工单创建失败：{result.message or result.biz_code or '未知原因'}。您也可以转人工处理。"
            return ActionResult(updated_slots={"ticket_create_success": "false", "ticket_message": message})

        data = result.data if isinstance(result.data, dict) else {}
        ticket_no = str(data.get("ticket_no") or "")
        return ActionResult(updated_slots={
            "ticket_create_success": "true" if ticket_no else "false",
            "ticket_no": ticket_no,
            "ticket_message": "" if ticket_no else "工单创建失败：中台未返回工单编号。",
        })
