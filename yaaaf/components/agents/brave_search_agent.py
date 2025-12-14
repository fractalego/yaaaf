import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import BraveExecutor
from yaaaf.components.agents.prompts import brave_search_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class BraveSearchAgent(ToolBasedAgent):
    """Web search agent using Brave Search API."""

    def __init__(self, client: BaseClient):
        """Initialize Brave search agent."""
        super().__init__(client, BraveExecutor())
        self._system_prompt = brave_search_agent_prompt_template
        self._output_tag = "```text"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Searches the web using Brave Search API"

    def get_description(self) -> str:
        return f"""
Brave Search agent: {self.get_info()}.
This agent searches the web for information using the Brave Search API and returns relevant results.
To call this agent write {self.get_opening_tag()} SEARCH QUERY {self.get_closing_tag()}
Write a clear search query for the information you need.
        """
