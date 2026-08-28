"""
金融知识提供者（Provider）：
- api.*  实时业务数据（调用金融中台，需配合聚焦卡片）
- api.loan_product / api.wealth_product  产品列表（无需卡片）
- faq.default  客服库 cs_faq 关键词检索
- rag.default  客服库 cs_knowledge_doc 关键词检索
"""
import json
import logging
import re
from typing import Any

from sqlalchemy import text

from financecs.config.settings import settings
from financecs.domain.state import DialogueState
from financecs.infrastructure import db_client
from financecs.infrastructure.finance_client import finance_client
from financecs.knowledge.provider.provider import Provider, KnowledgeChunk

logger = logging.getLogger(__name__)


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ===================== 实时业务数据（需聚焦卡片） =====================

class ApiAccountProvider(Provider):
    provider_id = "api.account"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        if state.focused_object is None:
            return [KnowledgeChunk(content="未获取到账户信息")]
        account_no = state.focused_object.id
        result = await finance_client.call(state.sender_id, "GET", f"/api/v1/accounts/{account_no}")
        if not result.ok:
            return [KnowledgeChunk(content=f"账户信息查询失败：{result.message}")]
        return [KnowledgeChunk(content=f"账户信息：\n{_dump(result.data)}")]


class ApiTransactionProvider(Provider):
    provider_id = "api.transaction"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        if state.focused_object is None:
            return [KnowledgeChunk(content="未获取到交易信息")]
        transaction_no = state.focused_object.id
        result = await finance_client.call(state.sender_id, "GET", f"/api/v1/transactions/{transaction_no}")
        if not result.ok:
            return [KnowledgeChunk(content=f"交易信息查询失败：{result.message}")]
        return [KnowledgeChunk(content=f"交易信息：\n{_dump(result.data)}")]


class ApiLoanApplicationProvider(Provider):
    provider_id = "api.loan_application"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        if state.focused_object is None:
            return [KnowledgeChunk(content="未获取到贷款申请信息")]
        application_no = state.focused_object.id
        result = await finance_client.call(state.sender_id, "GET", f"/api/v1/loan/applications/{application_no}")
        if not result.ok:
            return [KnowledgeChunk(content=f"贷款申请查询失败：{result.message}")]
        return [KnowledgeChunk(content=f"贷款申请信息：\n{_dump(result.data)}")]


class ApiTicketProvider(Provider):
    provider_id = "api.ticket"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        if state.focused_object is None:
            return [KnowledgeChunk(content="未获取到工单信息")]
        ticket_no = state.focused_object.id
        result = await finance_client.call(state.sender_id, "GET", f"/api/v1/support/tickets/{ticket_no}")
        if not result.ok:
            return [KnowledgeChunk(content=f"工单查询失败：{result.message}")]
        return [KnowledgeChunk(content=f"工单信息：\n{_dump(result.data)}")]


# ===================== 产品列表（无需卡片） =====================

class ApiLoanProductProvider(Provider):
    provider_id = "api.loan_product"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        result = await finance_client.call(state.sender_id, "GET", "/api/v1/loan/products",
                                           params={"product_status": "active"})
        if not result.ok:
            return [KnowledgeChunk(content=f"贷款产品查询失败：{result.message}")]
        data = result.data if isinstance(result.data, dict) else {}
        products = data.get("list") or []
        return [KnowledgeChunk(content=f"在售贷款产品：\n{_dump(products[:10])}")]


class ApiWealthProductProvider(Provider):
    provider_id = "api.wealth_product"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        result = await finance_client.call(state.sender_id, "GET", "/api/v1/wealth/products",
                                           params={"product_status": "selling"})
        if not result.ok:
            return [KnowledgeChunk(content=f"理财产品查询失败：{result.message}")]
        data = result.data if isinstance(result.data, dict) else {}
        products = data.get("list") or []
        return [KnowledgeChunk(content=f"在售理财产品：\n{_dump(products[:10])}")]


# ===================== FAQ / 知识库（客服库检索） =====================

def _tokenize(message: str) -> list[str]:
    """简单分词：抽取中文连续片段 + 英文数字，供关键词命中计分"""
    if not message:
        return []
    segments = re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", message)
    return segments


def _score(content: str, keywords: str, message: str) -> int:
    score = 0
    lowered = message.lower()
    if keywords:
        for kw in re.split(r"[,，;；\s]+", keywords):
            kw = kw.strip()
            if kw and kw.lower() in lowered:
                score += 3
    # 标题/问题中的字命中
    for ch in set(re.findall(r"[\u4e00-\u9fff]", content[:40])):
        if ch in message:
            score += 1
    return score


class FaqDefaultProvider(Provider):
    provider_id = "faq.default"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        message = ""
        if state.pending_turn is not None and state.pending_turn.user_message.text:
            message = state.pending_turn.user_message.text
        rows = await self._load_faqs()
        if not rows:
            return [KnowledgeChunk(content="未检索到相关问题")]
        scored = []
        for row in rows:
            s = _score(row["question"], row["keywords"] or "", message)
            if s > 0:
                scored.append((s, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:3]
        if not top:
            return [KnowledgeChunk(content="未检索到相关问题")]
        lines = []
        for _, row in top:
            lines.append(f"问：{row['question']}\n答：{row['answer']}")
        return [KnowledgeChunk(content="FAQ 检索结果：\n" + "\n\n".join(lines))]

    @staticmethod
    async def _load_faqs() -> list[dict[str, Any]]:
        try:
            async with db_client.session_factory() as session:
                cursor = await session.execute(
                    text("SELECT question, answer, keywords FROM cs_faq WHERE status='active' ORDER BY sort_no ASC"))
                return [dict(row._mapping) for row in cursor.fetchall()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载 FAQ 失败: %s", exc)
            return []


class RagDefaultProvider(Provider):
    provider_id = "rag.default"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        message = ""
        if state.pending_turn is not None and state.pending_turn.user_message.text:
            message = state.pending_turn.user_message.text
        docs = await self._load_docs()
        if not docs:
            return [KnowledgeChunk(content="未检索到相关知识")]
        scored = []
        for doc in docs:
            s = _score(doc["title"], doc["keywords"] or "", message)
            # 正文关键词补充计分
            for kw in re.split(r"[,，;；\s]+", doc["keywords"] or ""):
                if kw and kw.lower() in message.lower():
                    s += 1
            if s > 0:
                scored.append((s, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:2]
        if not top:
            return [KnowledgeChunk(content="未检索到相关知识")]
        lines = [f"【{row['title']}】\n{row['content']}" for _, row in top]
        return [KnowledgeChunk(content="知识库检索结果：\n" + "\n\n".join(lines))]

    @staticmethod
    async def _load_docs() -> list[dict[str, Any]]:
        try:
            async with db_client.session_factory() as session:
                cursor = await session.execute(
                    text("SELECT title, content, keywords FROM cs_knowledge_doc WHERE status='active'"))
                return [dict(row._mapping) for row in cursor.fetchall()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载知识库失败: %s", exc)
            return []
