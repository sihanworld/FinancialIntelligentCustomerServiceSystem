from financecs.chitchat.responder import ChitChatResponder
from financecs.domain.messages import BotMessage
from financecs.domain.state import DialogueState


class ChitChatHandler:

    def __init__(self, chatchat_responder: ChitChatResponder):
        self._chatchat_responder = chatchat_responder

    async def handle(self,
                     chat: str,
                     state: DialogueState) -> list[BotMessage]:
        bot_messages = await self._chatchat_responder.response(chat, state)

        return bot_messages
