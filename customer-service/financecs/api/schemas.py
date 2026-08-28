"""
定义接口数据模型：和前端进行交互
"""
from typing import Any

from pydantic import BaseModel

from financecs.domain.messages import ChatHistoryMessage


class ChatObject(BaseModel):
    id: str       # 业务编号（账户号/卡号/交易流水号/申请编号/工单编号/产品代码）
    title: str    # 卡片标题
    type: str     # account / bank_card / transaction / loan_product / wealth_product / loan_application / ticket
    attributes: dict[str, Any] = {}


class ChatBotMessage(BaseModel):
    text: str
    object: ChatObject | None = None


class ChatRequest(BaseModel):
    """聊天请求接口数据模型"""
    sender_id: str
    text: str | None = None
    object: ChatObject | None = None


class ChatResponse(BaseModel):
    """聊天响应接口数据模型"""
    message_id: str
    messages: list[ChatBotMessage]


class ChatHistoryResponse(BaseModel):
    sender_id: str
    messages: list[ChatHistoryMessage]


class SessionCreateRequest(BaseModel):
    """创建新会话请求"""
    sender_id: str
    trigger_onboarding: bool = True


class SessionCreateResponse(BaseModel):
    """创建新会话响应"""
    session_id: str
    messages: list[ChatBotMessage]


class SessionStateResponse(BaseModel):
    """当前会话状态响应"""
    sender_id: str
    session_id: str | None = None
    active_task: dict[str, Any] | None = None
    paused_tasks: list[dict[str, Any]] = []
    focused_object: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    finance_api: str = "unknown"
