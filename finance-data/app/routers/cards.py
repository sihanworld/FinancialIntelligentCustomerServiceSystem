"""银行卡/信用卡查询与挂失接口（智能客服扩展）。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path
from pydantic import BaseModel, Field

from ..database import db_cursor, fetch_one
from ..dependencies import RequestContext, get_request_context
from ..errors import conflict, forbidden, not_found
from ..idempotency import idempotent_result, save_idempotent_result
from ..response import ok
from ..utils import format_datetime, local_now, make_no, serialize_row

router = APIRouter(prefix="/api/v1", tags=["cards"])


class CardLossReportRequest(BaseModel):
    request_no: str = Field(description="请求唯一编号，用于写接口幂等控制")
    loss_reason: str = Field(default="卡片丢失", description="挂失原因")


def _card_by_no(card_no: str, ctx: RequestContext) -> dict[str, Any]:
    card = fetch_one("SELECT * FROM bank_card WHERE card_no = %s", (card_no,))
    if card is None:
        raise not_found("CARD_NOT_FOUND", "卡片不存在")
    customer = fetch_one(
        "SELECT customer_no FROM customer WHERE id = %s", (card["customer_id"],)
    )
    if ctx.auth_type == "customer" and (
        customer is None or customer["customer_no"] != ctx.principal_no
    ):
        raise forbidden("CARD_SCOPE_FORBIDDEN", "客户只能访问本人卡片")
    return card


@router.get("/cards/{card_no}", summary="按卡号查询卡片与绑定账户")
def get_card(
    card_no: Annotated[str, Path(description="银行卡/信用卡卡号")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    card = _card_by_no(card_no, ctx)
    account = fetch_one(
        "SELECT account_no, account_status FROM bank_account WHERE id = %s",
        (card["account_id"],),
    )
    customer = fetch_one(
        "SELECT customer_no, customer_name FROM customer WHERE id = %s",
        (card["customer_id"],),
    )
    data = serialize_row(card)
    data["account_no"] = account["account_no"] if account else None
    data["account_status"] = account["account_status"] if account else None
    data["customer_no"] = customer["customer_no"] if customer else None
    return ok(data, ctx.request_id)


@router.post("/cards/{card_no}/loss-report", summary="卡片挂失")
def report_card_loss(
    card_no: Annotated[str, Path(description="银行卡/信用卡卡号")],
    body: Annotated[CardLossReportRequest, Body(description="接口请求体")],
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    cached = idempotent_result(
        ctx.channel_code, "card_loss_report", body.request_no, body.model_dump()
    )
    if cached is not None:
        return ok(cached, ctx.request_id)

    card = _card_by_no(card_no, ctx)
    if card["card_status"] != "active":
        raise conflict("CARD_STATUS_FORBIDDEN", "卡片当前状态不允许挂失")

    now = local_now()
    loss_report_no = make_no("LOSS")
    with db_cursor() as (_, cursor):
        cursor.execute(
            "UPDATE bank_card SET card_status = 'lost', updated_at = %s WHERE id = %s",
            (now, card["id"]),
        )
    data = {
        "card_no": card_no,
        "card_status": "lost",
        "loss_report_no": loss_report_no,
        "loss_reason": body.loss_reason,
        "loss_time": format_datetime(now),
    }
    save_idempotent_result(
        ctx.channel_code, "card_loss_report", body.request_no, body.model_dump(), data
    )
    return ok(data, ctx.request_id)
