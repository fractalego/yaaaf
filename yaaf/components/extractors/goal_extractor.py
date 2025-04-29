from yaaf.components.client import BaseClient
from yaaf.components.data_types import Messages, PromptTemplate
from yaaf.components.extractors.base_extractor import BaseExtractor
from yaaf.components.extractors.prompts import goal_extractor_prompt


class GoalExtractor(BaseExtractor):
    """
    GoalExtractor is a class that extracts the goal from a given message.
    It uses a specific prompt template to guide the extraction process.
    """

    _goal_extractor_prompt: PromptTemplate = goal_extractor_prompt

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client

    async def extract(self, messages: Messages) -> str:
        instructions = Messages().add_system_prompt(
            self._goal_extractor_prompt.complete(messages=str(messages))
        )
        instructions = instructions.add_user_utterance(
            "Write below the goal in a single sentence"
        )
        answer = await self._client.predict(instructions)
        return answer
