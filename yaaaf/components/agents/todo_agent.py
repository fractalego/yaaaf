import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import TodoExecutor
from yaaaf.components.agents.prompts import todo_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class TodoAgent(ToolBasedAgent):
    """Agent that manages todo lists and task tracking."""

    def __init__(self, client: BaseClient, agents_and_sources_and_tools_list: str = ""):
        """Initialize todo agent."""
        super().__init__(client, TodoExecutor(agents_and_sources_and_tools_list))
        self._system_prompt = todo_agent_prompt_template
        self._output_tag = "```table"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Manages todo lists and task tracking"

    def get_description(self) -> str:
        return f"""
Todo agent: {self.get_info()}.
This agent can:
- Create and manage todo lists
- Track task status and priorities
- Organize tasks by agent assignments
- Generate task summary reports

To call this agent write {self.get_opening_tag()} TODO_REQUEST {self.get_closing_tag()}
Describe what kind of todo list or task management you need.
        """