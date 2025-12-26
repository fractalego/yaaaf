import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import CodeEditExecutor
from yaaaf.components.agents.prompts import code_edit_agent_prompt_template
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class CodeEditAgent(ToolBasedAgent):
    """Agent that performs code editing operations.

    This agent can view, create, and modify files using precise string
    replacement operations. It's designed for software engineering tasks
    like bug fixes and code modifications.

    Supported operations:
    - view: Read file contents with line numbers
    - create: Create new files with content
    - str_replace: Replace exact strings in files
    """

    def __init__(self, client: BaseClient, allowed_directories: list[str] | None = None):
        """Initialize code edit agent.

        Args:
            client: The LLM client to use
            allowed_directories: List of directories where editing is allowed.
                                If None, defaults to current working directory.
        """
        super().__init__(client, CodeEditExecutor(allowed_directories))
        self._system_prompt = code_edit_agent_prompt_template
        self._output_tag = "```code_edit"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Performs code editing operations (view, create, str_replace)"

    def get_description(self) -> str:
        return f"""
Code Edit Agent: {self.get_info()} on source files.
Use this agent when you need to:
- View file contents with line numbers
- Create new source files
- Make precise string replacements in existing files
- Fix bugs by modifying code
- Add new functions or classes to existing files
- Refactor code by replacing patterns

This agent uses exact string matching for replacements, ensuring precise edits.
The agent will refuse to edit files outside allowed directories for security.

Accepts: text (file path and operation details)
Produces: text (operation result or file contents)

To call this agent write {self.get_opening_tag()} CODE_EDIT_TASK_DESCRIPTION {self.get_closing_tag()}
Describe what file operation you need to perform.
        """
