import logging
import subprocess
import os
from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.agents.prompts import bash_agent_prompt_template
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages, Note
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class BashAgent(BaseAgent):
    _system_prompt: PromptTemplate = bash_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag, task_paused_tag]
    _output_tag = "```bash"
    _stop_sequences = [task_completed_tag, task_paused_tag]
    _max_steps = 5

    def __init__(self, client: BaseClient) -> None:
        self._client = client

    def is_paused(self, answer: str) -> bool:
        """Check if the agent has paused execution to wait for user confirmation."""
        return task_paused_tag in answer

    def _is_safe_command(self, command: str) -> bool:
        """Check if a command is considered safe for execution."""
        # List of potentially dangerous commands/patterns
        dangerous_patterns = [
            "rm -rf",
            "sudo",
            "su ",
            "chmod +x",
            "curl",
            "wget",
            "pip install",
            "npm install",
            "apt install",
            "yum install",
            "systemctl",
            "service",
            "kill",
            "pkill",
            "killall",
            "shutdown",
            "reboot",
            "dd ",
            "mkfs",
            "format",
            "fdisk",
            "mount",
            "umount",
            "chown",
            "passwd",
            "adduser",
            "userdel",
            "groupadd",
            "crontab",
            "history -c",
            "export",
            "unset",
            "alias",
            "source",
            ". ",
            "exec",
            "eval",
            "python -c",
            "python3 -c",
            "bash -c",
            "sh -c",
            "> /dev/",
            "| dd",
        ]

        command_lower = command.lower().strip()

        # Check for dangerous patterns
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return False

        # Check for suspicious redirections
        if any(redirect in command for redirect in ["> /", ">> /", "| tee /"]):
            return False

        # Check for command chaining with potentially dangerous operations
        if any(op in command for op in ["; rm", "&& rm", "|| rm", "; sudo", "&& sudo"]):
            return False

        return True

    def _execute_command(self, command: str) -> tuple[str, str, int]:
        """Execute a bash command and return stdout, stderr, and return code."""
        try:
            _logger.info(f"BashAgent executing command: {command}")

            # Execute the command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=os.getcwd(),
            )

            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired:
            return "", "Command timed out after 30 seconds", 1
        except Exception as e:
            return "", f"Error executing command: {str(e)}", 1

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        messages = messages.add_system_prompt(self._system_prompt)

        for step in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

            # Handle empty responses
            if answer.strip() == "":
                break

            # Extract bash command from the response
            bash_command = get_first_text_between_tags(answer, self._output_tag, "```")

            if bash_command:
                bash_command = bash_command.strip()

                # Add command to notes for visibility
                if notes is not None:
                    model_name = getattr(self._client, "model", None)
                    note = Note(
                        message=f"Proposed bash command:\n```bash\n{bash_command}\n```",
                        artefact_id=None,
                        agent_name=self.get_name(),
                        model_name=model_name,
                    )
                    notes.append(note)

                # Check if command is safe
                if not self._is_safe_command(bash_command):
                    safety_message = f"⚠️ This command appears potentially dangerous: `{bash_command}`\n\nDo you want to proceed? (This command could modify system files, install software, or perform other potentially risky operations) {task_paused_tag}"
                    return safety_message

                # Ask for user confirmation before executing
                confirmation_message = f"I want to execute the following bash command:\n\n```bash\n{bash_command}\n```\n\nDo you want me to proceed with this command? {task_paused_tag}"
                return confirmation_message

            # Check if agent is providing final output without command
            if task_completed_tag in answer:
                return answer

            # Check if agent is paused (should have been handled above)
            if self.is_paused(answer):
                return answer

            # Continue the conversation
            messages = messages.add_user_utterance(
                f"Your response: {answer}\n\n"
                f"Please provide a bash command using the ```bash format, or if the task is complete, use {task_completed_tag}.\n"
                f"If you need user input, ask a question and use {task_paused_tag}."
            )

        return f"Could not generate a suitable bash command for the requested task. {task_completed_tag}"

    async def execute_confirmed_command(
        self, command: str, notes: Optional[List[Note]] = None
    ) -> str:
        """Execute a command that has been confirmed by the user."""
        stdout, stderr, returncode = self._execute_command(command)

        # Prepare the result message
        result_message = f"Command executed: `{command}`\n\n"

        if returncode == 0:
            result_message += "✅ Command completed successfully\n\n"
            if stdout:
                result_message += f"**Output:**\n```\n{stdout}\n```\n\n"
        else:
            result_message += f"❌ Command failed with return code {returncode}\n\n"
            if stderr:
                result_message += f"**Error:**\n```\n{stderr}\n```\n\n"
            if stdout:
                result_message += f"**Output:**\n```\n{stdout}\n```\n\n"

        # Add execution result to notes
        if notes is not None:
            model_name = getattr(self._client, "model", None)
            note = Note(
                message=result_message,
                artefact_id=None,
                agent_name=self.get_name(),
                model_name=model_name,
            )
            notes.append(note)

        result_message += task_completed_tag
        return result_message

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent can execute bash commands for filesystem operations"

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

⚠️ IMPORTANT: This agent will ask for user confirmation before executing any command for security reasons.

To call this agent write {self.get_opening_tag()} FILESYSTEM_TASK_DESCRIPTION {self.get_closing_tag()}
Describe what you need to accomplish with the filesystem in clear English.
        """
