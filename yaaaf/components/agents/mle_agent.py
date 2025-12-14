import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import PythonExecutor
from yaaaf.components.agents.prompts import (
    mle_agent_prompt_template_without_model,
    mle_agent_prompt_template_with_model,
)
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class MleAgent(ToolBasedAgent):
    """Agent that executes machine learning Python code."""

    def __init__(self, client: BaseClient):
        """Initialize MLE agent."""
        super().__init__(client, PythonExecutor(output_type="mixed"))
        self._output_tag = "```python"
        
        # Use model-specific prompt template
        try:
            self._system_prompt = mle_agent_prompt_template_with_model
        except Exception:
            self._system_prompt = mle_agent_prompt_template_without_model

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Executes machine learning and data science Python code"

    def get_description(self) -> str:
        return f"""
MLE agent: {self.get_info()}.
This agent can:
- Execute Python ML/DS code
- Train machine learning models
- Perform data analysis
- Create ML pipelines
- Generate predictions and insights

To call this agent write {self.get_opening_tag()} ML_TASK_DESCRIPTION {self.get_closing_tag()}
Describe the machine learning or data science task you want to accomplish.
        """