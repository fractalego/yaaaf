import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import BashExecutor
from yaaaf.components.agents.prompts import bash_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class BashAgent(ToolBasedAgent):
    """Agent that executes bash commands with safety features."""

    def __init__(self, client: BaseClient):
        """Initialize bash agent."""
        super().__init__(client, BashExecutor())
        self._system_prompt = bash_agent_prompt_template
        self._output_tag = "```bash"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Executes bash commands for filesystem operations"

    def get_description(self) -> str:
        return f"""
Bash agent: {self.get_info()} like reading files, listing directories, and writing content.
Use this agent when you need to:
- List directory contents (ls, find)
- Read file contents (cat, head, tail)
- Write content to files (echo, tee)
- Create directories (mkdir)
- Move or copy files (mv, cp)
- Search file contents (grep)
- Check file permissions (ls -l)
- Navigate filesystem (pwd, cd)

⚠️ IMPORTANT: This agent includes safety checks for potentially dangerous commands.

To call this agent write {self.get_opening_tag()} FILESYSTEM_TASK_DESCRIPTION {self.get_closing_tag()}
Describe what you need to accomplish with the filesystem in clear English.
        """