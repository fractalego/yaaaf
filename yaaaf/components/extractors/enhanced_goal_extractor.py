import re
from typing import Dict, Optional
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.components.extractors.base_extractor import BaseExtractor
from yaaaf.components.extractors.prompts import enhanced_goal_extractor_prompt


class EnhancedGoalExtractor(BaseExtractor):
    """
    EnhancedGoalExtractor extracts both the goal and target artifact type from messages.
    """

    _enhanced_goal_prompt: PromptTemplate = enhanced_goal_extractor_prompt

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client

    async def extract(self, messages: Messages) -> Dict[str, str]:
        """Extract goal and target artifact type from messages.

        Returns:
            Dict with keys 'goal' and 'artifact_type'
        """
        instructions = Messages().add_system_prompt(
            self._enhanced_goal_prompt.complete(messages=str(messages))
        )
        instructions = instructions.add_user_utterance(
            "Extract the goal and artifact type according to the format specified."
        )

        response = await self._client.predict(instructions)
        return self._parse_response(response.message)

    def _parse_response(self, response: str) -> Dict[str, str]:
        """Parse the response to extract goal and artifact type."""
        result = {
            "goal": "",
            "artifact_type": "TABLE",  # Default
        }

        # Extract goal
        goal_match = re.search(r"Goal:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if goal_match:
            result["goal"] = goal_match.group(1).strip()

        # Extract artifact type
        artifact_match = re.search(
            r"Artifact Type:\s*(TABLE|IMAGE|TEXT|MODEL|TODO_LIST)",
            response,
            re.IGNORECASE,
        )
        if artifact_match:
            result["artifact_type"] = artifact_match.group(1).upper()

        return result
