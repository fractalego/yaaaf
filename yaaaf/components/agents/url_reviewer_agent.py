import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import ArtifactProcessorExecutor
from yaaaf.components.agents.prompts import url_retriever_agent_prompt_template_without_model
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class UrlReviewerAgent(ToolBasedAgent):
    """Agent that reviews URL-related artifacts and data."""

    def __init__(self, client: BaseClient):
        """Initialize URL reviewer agent."""
        super().__init__(client, ArtifactProcessorExecutor(client, "```table"))
        self._system_prompt = url_retriever_agent_prompt_template_without_model
        self._output_tag = "```table"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Reviews and analyzes URL-related artifacts and data"

    def get_description(self) -> str:
        return f"""
URL Reviewer agent: {self.get_info()}.
This agent can:
- Review URL content and artifacts
- Analyze web-related data
- Create summary tables of URL information
- Validate and process web content

To call this agent write {self.get_opening_tag()} URL_REVIEW_REQUEST {self.get_closing_tag()}
Describe what URL-related content you want reviewed or analyzed.
        """