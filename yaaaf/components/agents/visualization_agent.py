import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import PythonExecutor
from yaaaf.components.agents.prompts import (
    visualization_agent_prompt_template_without_model as visualization_agent_prompt_template,
)
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class VisualizationAgent(ToolBasedAgent):
    """Agent that creates data visualizations using Python and matplotlib."""

    def __init__(self, client: BaseClient):
        """Initialize visualization agent."""
        super().__init__(client, PythonExecutor(output_type="image"))
        self._system_prompt = visualization_agent_prompt_template
        self._output_tag = "```python"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Creates data visualizations using matplotlib"

    def get_description(self) -> str:
        return f"""
Visualization agent: {self.get_info()}.
This agent creates charts, graphs, and other visualizations from data using Python and matplotlib.
To call this agent write {self.get_opening_tag()} VISUALIZATION REQUEST {self.get_closing_tag()}
Describe what kind of visualization you want and reference any data artifacts.
        """
