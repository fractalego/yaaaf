import logging

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import CodeEditExecutor
from yaaaf.components.agents.prompts import get_code_edit_prompt_for_model
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class CodeEditAgent(ToolBasedAgent):
    """Unified agent that performs code editing operations and executes shell commands.

    This agent can view, create, and modify files using precise string
    replacement operations, and execute bash commands for testing and exploration.
    It's designed for software engineering tasks like bug fixes, code modifications,
    and running tests.

    Supported operations:
    - view: Read file contents with line numbers
    - create: Create new files with content
    - str_replace: Replace exact strings in files
    - bash: Execute shell commands (run tests, explore directories, etc.)
    """

    def __init__(self, client: BaseClient, allowed_directories: list[str] | None = None, allow_overwrite: bool = True):
        """Initialize code edit agent.

        Args:
            client: The LLM client to use
            allowed_directories: List of directories where editing is allowed.
                                If None, defaults to current working directory.
            allow_overwrite: If True, the 'create' operation can overwrite existing files.
                            Defaults to True for convenience.
        """
        super().__init__(client, CodeEditExecutor(allowed_directories, allow_overwrite=allow_overwrite))

        # Select prompt based on the model being used
        model_name = getattr(client, 'model', '') or ''
        self._system_prompt = get_code_edit_prompt_for_model(model_name)
        _logger.info(f"CodeEditAgent using prompt for model: {model_name}")

        # Set output tag based on model format
        if "devstral" in model_name.lower() or "mistral" in model_name.lower():
            self._output_tag = "[TOOL_CALLS]code_edit"
        else:
            self._output_tag = "```code_edit"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Performs code editing operations (view, create, str_replace) and executes shell commands (bash)"

    def get_description(self) -> str:
        return f"""
Code Edit Agent: {self.get_info()}.
Use this agent when you need to:
- View file contents with line numbers
- Create new source files
- Make precise string replacements in existing files
- Fix bugs by modifying code
- Add new functions or classes to existing files
- Refactor code by replacing patterns
- Run tests to verify fixes (bash commands)
- Explore directory structures (bash commands)
- Execute shell commands to check outputs

This agent uses exact string matching for replacements, ensuring precise edits.
The agent will refuse to edit files outside allowed directories for security.
Bash commands run in the working directory with optional virtual environment support.

Accepts: text (file path and operation details, or bash commands)
Produces: text (operation result, file contents, or command output)

To call this agent write {self.get_opening_tag()} CODE_EDIT_TASK_DESCRIPTION {self.get_closing_tag()}
Describe what file operation or bash command you need to perform.
        """
