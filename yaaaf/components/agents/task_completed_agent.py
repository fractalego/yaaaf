from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.decorators import handle_exceptions


class TaskCompletedAgent(BaseAgent):
    """
    A dummy agent whose only purpose is to return the task completed tag.
    This allows the orchestrator to explicitly signal task completion through tool calling.
    """

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        """Simply return the task completed tag."""
        return task_completed_tag

    @staticmethod
    def get_info() -> str:
        return "This agent signals that the task has been completed successfully"

    def get_description(self) -> str:
        return f"{self.get_info()}. Use this agent when you are confident that the task has been fully completed and no further actions are needed."