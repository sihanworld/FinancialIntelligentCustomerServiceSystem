"""
金融中台统一客户端：鉴权头 / 超时 / 重试 / 幂等 / 审计
所有 Action 与 api.* Provider 一律通过本客户端访问 finance-data 服务。
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from financecs.config.settings import settings
from financecs.infrastructure import http_client

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FinanceResult:
    ok: bool
    data: Any = None
    biz_code: str = ""
    message: str = ""
    http_status: int = 0
    request_id: str = field(default="")


class FinanceClient:

    def new_request_id(self) -> str:
        return uuid.uuid4().hex

    def _headers(self, sender_id: str, request_id: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {sender_id}",
            "X-Channel-Code": settings.finance_api_channel_code,
            "X-Request-Id": request_id,
        }

    async def call(self,
                   sender_id: str,
                   method: str,
                   path: str,
                   *,
                   params: dict[str, Any] | None = None,
                   json_body: dict[str, Any] | None = None,
                   request_id: str | None = None) -> FinanceResult:
        """
        调用金融中台接口。
        - 读接口（GET）：失败重试 finance_api_max_retries 次（指数退避）
        - 写接口（POST）：不重试（幂等号由调用方在 json_body.request_no 中提供）
        - 任何异常都转换为 FinanceResult(ok=False)，不向调用方抛出
        """
        url = settings.finance_api_base_url.rstrip("/") + path
        rid = request_id or self.new_request_id()
        headers = self._headers(sender_id, rid)
        method_upper = method.upper()
        attempts = 1 + (settings.finance_api_max_retries if method_upper == "GET" else 0)
        timeout = httpx.Timeout(settings.finance_api_timeout_read,
                                connect=settings.finance_api_timeout_connect)

        for attempt in range(attempts):
            start_ts = time.perf_counter()
            try:
                response = await http_client.http_client.request(
                    method_upper, url, params=params, json=json_body,
                    headers=headers, timeout=timeout)
                cost_ms = int((time.perf_counter() - start_ts) * 1000)

                try:
                    payload = response.json()
                except Exception:
                    payload = {}

                code = payload.get("code")
                if response.status_code < 400 and code == 0:
                    await self._audit(sender_id, method_upper, path, json_body,
                                      payload, response.status_code, str(code), cost_ms)
                    return FinanceResult(ok=True, data=payload.get("data"),
                                         biz_code=str(code), message=payload.get("message", ""),
                                         http_status=response.status_code, request_id=rid)

                await self._audit(sender_id, method_upper, path, json_body,
                                  payload, response.status_code, str(code), cost_ms)
                return FinanceResult(ok=False, data=payload.get("data"),
                                     biz_code=str(code), message=payload.get("message", "中台返回异常"),
                                     http_status=response.status_code, request_id=rid)

            except Exception as exc:  # noqa: BLE001 网络异常统一降级
                cost_ms = int((time.perf_counter() - start_ts) * 1000)
                logger.warning("金融中台调用异常 %s %s attempt=%s err=%s", method_upper, path, attempt, exc)
                if attempt < attempts - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                await self._audit(sender_id, method_upper, path, json_body,
                                  {"error": str(exc)}, 0, "NETWORK_ERROR", cost_ms)
                return FinanceResult(ok=False, biz_code="NETWORK_ERROR",
                                     message="金融业务系统暂时不可用，请稍后再试。", request_id=rid)

        return FinanceResult(ok=False, biz_code="NETWORK_ERROR",
                             message="金融业务系统暂时不可用，请稍后再试。", request_id=rid)

    async def _audit(self, sender_id: str, method: str, path: str,
                     request_body: dict[str, Any] | None, payload: dict[str, Any],
                     http_status: int, biz_code: str, cost_ms: int) -> None:
        """写 cs_action_audit（尽力而为：失败仅记日志，不影响主流程）"""
        try:
            from financecs.infrastructure import db_client

            if db_client.session_factory is None:
                return

            from sqlalchemy import text

            request_json = json.dumps(request_body or {}, ensure_ascii=False)[:8000]
            response_json = json.dumps(payload, ensure_ascii=False, default=str)[:8000]
            async with db_client.session_factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO cs_action_audit "
                        "(sender_id, action_name, method, url, request_json, response_json, http_status, biz_code, cost_ms) "
                        "VALUES (:sender_id, :action_name, :method, :url, :request_json, :response_json, :http_status, :biz_code, :cost_ms)"
                    ),
                    {
                        "sender_id": sender_id,
                        "action_name": "finance_api",
                        "method": method,
                        "url": path[:256],
                        "request_json": request_json,
                        "response_json": response_json,
                        "http_status": http_status,
                        "biz_code": biz_code,
                        "cost_ms": cost_ms,
                    },
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("写入审计日志失败: %s", exc)


finance_client = FinanceClient()
