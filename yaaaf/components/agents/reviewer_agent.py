import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import PythonExecutor
from yaaaf.components.agents.prompts import (
    reviewer_agent_prompt_template_without_model as reviewer_agent_prompt_template,
)
from yaaaf.components.extractors.artefact_extractor import ArtefactExtractor
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class ReviewerAgent(ToolBasedAgent):
    """Agent that reviews and executes Python code to validate results."""

    def __init__(self, client: BaseClient):
        """Initialize reviewer agent."""
        super().__init__(client, PythonExecutor(output_type="text"))
        self._system_prompt = reviewer_agent_prompt_template
        self._output_tag = "```python"
        
        # Reviewer agent needs artifact extraction capability
        self._artefact_extractor = ArtefactExtractor(client)

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Reviews and validates results by executing Python code"

    def get_description(self) -> str:
        return f"""
Reviewer agent: {self.get_info()}.
This agent can execute Python code to analyze, validate, or process data and results.
To call this agent write {self.get_opening_tag()} REVIEW REQUEST {self.get_closing_tag()}
Describe what you want to review or analyze and reference any data artifacts.
        """
