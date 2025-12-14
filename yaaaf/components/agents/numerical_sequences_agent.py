import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import NumericalExecutor
from yaaaf.components.agents.prompts import numerical_sequences_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class NumericalSequencesAgent(ToolBasedAgent):
    """Agent that analyzes and processes numerical sequences and data."""

    def __init__(self, client: BaseClient):
        """Initialize numerical sequences agent."""
        super().__init__(client, NumericalExecutor())
        self._system_prompt = numerical_sequences_agent_prompt_template
        self._output_tag = "```table"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Analyzes and processes numerical sequences and statistical data"

    def get_description(self) -> str:
        return f"""
Numerical Sequences agent: {self.get_info()}.
This agent can:
- Analyze numerical patterns and sequences
- Generate statistical summaries
- Process tabular numerical data
- Create data analysis reports

To call this agent write {self.get_opening_tag()} NUMERICAL_ANALYSIS_REQUEST {self.get_closing_tag()}
Describe what kind of numerical analysis or sequence processing you need.
        """