import logging

from financecs.chat_history.builder import ChatHistoryBuilder
from financecs.domain.contexts import TaskContext
from financecs.domain.messages import BotMessage, ChatHistoryMessage, UserMessage, ProcessedResult
from financecs.domain.state import DialogueState
from financecs.engines.dialogue_engine import DialogueEngine
from financecs.repository.dialogue_repository import DialogueRepository

logger = logging.getLogger(__name__)

# 敏感槽位：不对外暴露（状态查询接口过滤）
SENSITIVE_SLOTS = {"id_verify_info"}


class DialogueStateService:

    def __init__(self,
                 engine: DialogueEngine,
                 repository: DialogueRepository):
        self._engine = engine
        self._repository = repository

    # ================================================= 核心对话处理 =================================================

    async def process_message(self, user_message: UserMessage) -> ProcessedResult:
        """
        职责：处理对话消息的核心入口
        """
        # 1. 从数据库中读取当前用户的对话状态
        dialogue_state = await self._repository.load_state(user_message.sender_id)

        # 2. 引擎处理
        processed_result = await self._engine.handle_message(user_message, dialogue_state)

        # 3. 状态保存（降级：保存失败不阻断响应）
        await self._safe_save(user_message.sender_id, dialogue_state)

        return processed_result

    async def _safe_save(self, sender_id: str, dialogue_state: DialogueState) -> None:
        try:
            await self._repository.save_state(sender_id, dialogue_state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("对话状态保存失败（已降级，不影响本轮响应）: %s", exc)

    # ================================================= 会话管理 =================================================

    async def create_session(self, sender_id: str, trigger_onboarding: bool = True) -> tuple[str, list[BotMessage]]:
        """
        职责：创建新会话；可选触发 onboarding 欢迎流程（确定性执行，不经过 LLM）。
        """
        state = await self._repository.load_state(sender_id)

        # 1. 关闭旧会话并重置运行时状态
        if state.current_session_id is not None:
            state.close_current_session()
        state.reset_runtime_state_for_new_session()

        # 2. 开启新会话
        state.start_session()
        session_id = state.current_session_id

        # 3. 欢迎引导（执行 onboarding 流程的静态响应）
        bot_messages: list[BotMessage] = []
        if trigger_onboarding:
            try:
                task_handler = self._engine.task_handler
                flow = task_handler.flow_list.get_flow_by_id("onboarding")
                if flow is not None:
                    state.start_task(TaskContext(flow_id="onboarding", step_id="start"))
                    bot_messages = await task_handler.flow_executor.execute_flow(
                        state,
                        action_runner=task_handler.action_runner,
                        flow_list=task_handler.flow_list,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.exception("onboarding 执行失败（降级跳过）: %s", exc)

        await self._safe_save(sender_id, state)
        return session_id, bot_messages

    async def get_session_state(self, sender_id: str) -> dict:
        """
        职责：查询当前会话状态（激活流程、挂起流程、槽位、聚焦对象）
        """
        state = await self._repository.load_state(sender_id)
        flow_list = self._engine.task_handler.flow_list

        def describe_task(task: TaskContext) -> dict:
            flow = flow_list.get_flow_by_id(task.flow_id)
            slots = {k: v for k, v in task.slots.items() if k not in SENSITIVE_SLOTS}
            return {
                "flow_id": task.flow_id,
                "flow_name": flow.name if flow is not None else task.flow_id,
                "step_id": task.step_id,
                "slots": slots,
            }

        session = state.current_session()
        return {
            "sender_id": sender_id,
            "session_id": session.session_id if session is not None else None,
            "active_task": describe_task(state.active_task) if state.active_task is not None else None,
            "paused_tasks": [describe_task(task) for task in state.paused_tasks],
            "focused_object": state.focused_object.to_dict() if state.focused_object is not None else None,
        }

    # ================================================= 历史消息 =================================================

    async def get_chat_history(self, sender_id: str) -> list[ChatHistoryMessage]:
        """
        职责：查询该用户所有会话下的聊天内容
        """
        state = await self._repository.load_state(sender_id)

        final_chat_history_messages = []
        for session in state.sessions:
            for turn in session.turns:
                user_message = turn.user_message
                final_chat_history_messages.append(
                    ChatHistoryBuilder.build_chat_history(session.session_id, "user",
                                                          user_message.text, user_message.object))
                for bot_message in turn.bot_messages:
                    final_chat_history_messages.append(
                        ChatHistoryBuilder.build_chat_history(session.session_id, "bot",
                                                              bot_message.text, bot_message.object))

        return final_chat_history_messages
