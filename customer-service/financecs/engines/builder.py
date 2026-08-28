from pathlib import Path

from financecs.chitchat.handler import ChitChatHandler
from financecs.chitchat.responder import ChitChatResponder
from financecs.clarify.responder import ClarifyResponder
from financecs.engines.dialogue_engine import DialogueEngine
from financecs.knowledge.handler import KnowledgeHandler
from financecs.knowledge.intents import KNOWLEDGE_INTENTS
from financecs.knowledge.provider.knowledge import (
    ApiAccountProvider,
    ApiLoanApplicationProvider,
    ApiLoanProductProvider,
    ApiTicketProvider,
    ApiTransactionProvider,
    ApiWealthProductProvider,
    FaqDefaultProvider,
    RagDefaultProvider,
)
from financecs.knowledge.provider.register import KnowledgeRegister
from financecs.knowledge.resonder import KnowledgeResponder
from financecs.plan.planner import TurnPlanner
from financecs.plan.validator import TurnPlanValidator
from financecs.task.action.builder import build_action_runner
from financecs.task.commands.processor import CommandProcessor
from financecs.task.flows.executor import FlowExecutor
from financecs.task.flows.loader import FlowLoader
from financecs.task.handler import TaskHandler

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]

FLOW_CONFIG_DIR = PROJECT_ROOT_DIR / "flow_config"


def build_dialogue_engine():
    # 1. 加载流程（金融版 YAML）
    flow_list = FlowLoader().load_multi_yaml(
        [FLOW_CONFIG_DIR / yaml for yaml in ("system_flows.yml", "user_flows.yml")])

    return DialogueEngine(
        turn_planner=TurnPlanner(),
        turn_plan_validator=TurnPlanValidator(),
        clarify_responder=ClarifyResponder(),
        task_handler=TaskHandler(
            flow_list=flow_list,
            command_processor=CommandProcessor(),
            flow_executor=FlowExecutor(),
            action_runner=build_action_runner()
        ),
        knowledge_handler=KnowledgeHandler(
            knowledge_intents=KNOWLEDGE_INTENTS,
            knowledge_register=KnowledgeRegister(
                providers=[
                    ApiAccountProvider(),
                    ApiTransactionProvider(),
                    ApiLoanApplicationProvider(),
                    ApiTicketProvider(),
                    ApiLoanProductProvider(),
                    ApiWealthProductProvider(),
                    FaqDefaultProvider(),
                    RagDefaultProvider(),
                ]
            ),
            knowledge_responder=KnowledgeResponder()
        ),
        chitchat_handler=ChitChatHandler(
            chatchat_responder=ChitChatResponder()
        )
    )
