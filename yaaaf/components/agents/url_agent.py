import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import URLExecutor
from yaaaf.components.agents.prompts import url_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class URLAgent(ToolBasedAgent):
    """Agent that fetches and analyzes content from URLs."""

    def __init__(self, client: BaseClient):
        """Initialize URL agent."""
        super().__init__(client, URLExecutor())
        self._system_prompt = url_agent_prompt_template
        self._output_tag = "```url"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Fetches and analyzes content from web URLs"

    def get_description(self) -> str:
        return f"""
URL agent: {self.get_info()}.
This agent can:
- Fetch content from web pages
- Extract and clean text content
- Parse HTML structure
- Provide summaries of web content

To call this agent write {self.get_opening_tag()} URL_TO_FETCH {self.get_closing_tag()}
Provide the full URL you want to fetch and analyze.
        """