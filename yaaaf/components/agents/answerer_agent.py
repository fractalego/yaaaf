import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import ArtifactProcessorExecutor
from yaaaf.components.agents.prompts import answerer_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class AnswererAgent(ToolBasedAgent):
    """Agent that processes artifacts and provides answers."""

    def __init__(self, client: BaseClient):
        """Initialize answerer agent."""
        super().__init__(client, ArtifactProcessorExecutor(client, "```table"))
        self._system_prompt = answerer_agent_prompt_template
        self._output_tag = "```table"
        self.set_budget(1)

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Processes artifacts and provides structured answers"

    def get_description(self) -> str:
        return f"""
Answerer agent: {self.get_info()}.
This agent can:
- Process and analyze artifacts
- Create structured responses
- Generate summary tables
- Provide comprehensive answers

To call this agent write {self.get_opening_tag()} ANSWER_REQUEST {self.get_closing_tag()}
Describe what you want the agent to analyze or answer.

IMPORTANT: This agent processes artifacts automatically. Include artifact references in your instruction using the format:
<artefact type='table'>artifact_id</artefact> or <artefact type='text'>artifact_id</artefact>
        """