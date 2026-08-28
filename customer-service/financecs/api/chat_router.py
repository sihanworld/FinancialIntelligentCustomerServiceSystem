"""
定义路由（金融智能客服）
- POST /api/chat           对话（非流式）
- POST /api/chat/stream    对话（SSE 流式）
- GET  /api/chat/history   历史消息
- POST /api/sessions       创建新会话
- GET  /api/sessions/state 当前会话状态
- GET  /health             健康检查
"""
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from financecs.api.dependencies import DialogueStateServiceDep
from financecs.api.schemas import (
    ChatBotMessage,
    ChatHistoryResponse,
    ChatObject,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStateResponse,
)
from financecs.config.settings import settings
from financecs.domain.messages import FocusedObject, MessageType, ProcessedResult, UserMessage
from financecs.infrastructure import http_client

logger = logging.getLogger(__name__)

router = APIRouter()


# ================================================= 健康检查 =================================================

@router.get("/health", response_model=HealthResponse)
async def health_endpoint():
    finance_status = "unknown"
    try:
        response = await http_client.http_client.get(f"{settings.finance_api_base_url.rstrip('/')}/health",
                                                     timeout=5)
        finance_status = "ok" if response.status_code == 200 else f"http_{response.status_code}"
    except Exception as exc:  # noqa: BLE001
        finance_status = f"error: {type(exc).__name__}"
    return HealthResponse(status="ok", finance_api=finance_status)


# ================================================= 对话（非流式） =================================================

@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest, service: DialogueStateServiceDep):
    user_message = _build_user_message(chat_request)
    processed_result = await service.process_message(user_message)
    return _build_chat_response(processed_result)


# ================================================= 对话（SSE 流式） =================================================

@router.post("/api/chat/stream")
async def chat_stream_endpoint(chat_request: ChatRequest, service: DialogueStateServiceDep):
    user_message = _build_user_message(chat_request)

    async def event_stream():
        try:
            processed_result = await service.process_message(user_message)
            yield _sse_event("message_start", {"message_id": processed_result.message_id})
            for bot_message in processed_result.messages:
                payload = _bot_message_payload(bot_message)
                # 分片推送文本，前端可获得渐进式渲染效果
                text = payload.get("text") or ""
                chunk_size = 24
                for i in range(0, max(len(text), 1), chunk_size):
                    chunk = text[i:i + chunk_size]
                    if chunk:
                        yield _sse_event("delta", {"text": chunk})
                        await asyncio.sleep(0.015)
                yield _sse_event("message_end", payload)
            yield _sse_event("done", {"message_id": processed_result.message_id})
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE 轮次处理失败")
            yield _sse_event("error", {"code": "INTERNAL_ERROR", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ================================================= 历史消息 =================================================

@router.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history_endpoint(sender_id: str, service: DialogueStateServiceDep):
    chat_history_messages = await service.get_chat_history(sender_id)
    return ChatHistoryResponse(sender_id=sender_id, messages=chat_history_messages)


# ================================================= 会话管理 =================================================

@router.post("/api/sessions", response_model=SessionCreateResponse)
async def create_session_endpoint(request: SessionCreateRequest, service: DialogueStateServiceDep):
    session_id, bot_messages = await service.create_session(request.sender_id, request.trigger_onboarding)
    return SessionCreateResponse(
        session_id=session_id,
        messages=[
            ChatBotMessage(
                text=msg.text,
                object=ChatObject(
                    id=msg.object.id, type=msg.object.type, title=msg.object.title,
                    attributes=msg.object.attributes) if msg.object is not None else None,
            )
            for msg in bot_messages
        ],
    )


@router.get("/api/sessions/state", response_model=SessionStateResponse)
async def get_session_state_endpoint(sender_id: str, service: DialogueStateServiceDep):
    state_dict = await service.get_session_state(sender_id)
    return SessionStateResponse(**state_dict)


# ================================================= 模型转换 =================================================

def _build_user_message(chat_request: ChatRequest) -> UserMessage:
    return UserMessage(
        sender_id=chat_request.sender_id,
        message_id=str(uuid.uuid4().hex),
        type=MessageType.OBJECT if chat_request.object is not None else MessageType.TEXT,
        text=chat_request.text,
        object=FocusedObject(
            id=chat_request.object.id,
            type=chat_request.object.type,
            title=chat_request.object.title,
            attributes=chat_request.object.attributes,
        ) if chat_request.object is not None else None,
    )


def _build_chat_response(processed_result: ProcessedResult) -> ChatResponse:
    return ChatResponse(
        message_id=processed_result.message_id,
        messages=[
            ChatBotMessage(
                text=bot_message.text,
                object=ChatObject(
                    id=bot_message.object.id,
                    type=bot_message.object.type,
                    title=bot_message.object.title,
                    attributes=bot_message.object.attributes,
                ) if bot_message.object is not None else None,
            )
            for bot_message in processed_result.messages
        ],
    )


def _bot_message_payload(bot_message) -> dict:
    return {
        "text": bot_message.text,
        "object": {
            "id": bot_message.object.id,
            "type": bot_message.object.type,
            "title": bot_message.object.title,
            "attributes": bot_message.object.attributes,
        } if bot_message.object is not None else None,
    }
