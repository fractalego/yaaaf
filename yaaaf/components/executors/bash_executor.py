import logging
import subprocess
import os
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class BashExecutor(ToolExecutor):
    """Executor for bash command execution."""

    def __init__(self):
        """Initialize bash executor."""
        self._storage = ArtefactStorage()
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for bash execution."""
        return {
            "messages": messages,
            "notes": notes or [],
            "working_dir": os.getcwd()
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract bash command from response."""
        command = get_first_text_between_tags(response, "```bash", "```")
        if command and not self._is_safe_command(command):
            # Return None to indicate unsafe command - this will be handled by the reflection engine
            return None
        return command
    
    def _is_safe_command(self, command: str) -> bool:
        """Check if a command is considered safe for execution."""
        dangerous_patterns = [
            "rm -rf", "sudo", "su ", "chmod +x", "curl", "wget", "pip install",
            "npm install", "apt install", "yum install", "systemctl", "service",
            "kill", "pkill", "killall", "shutdown", "reboot", "dd ", "mkfs",
            "format", "fdisk", "mount", "umount", "chown", "passwd", "adduser",
            "userdel", "groupadd", "crontab", "history -c", "export", "unset",
            "alias", "source", ". ", "exec", "eval", "python -c", "python3 -c",
            "bash -c", "sh -c", "> /dev/", "| dd"
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

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Execute bash command."""
        try:
            # Change to working directory if specified
            working_dir = context.get("working_dir", os.getcwd())
            
            # Execute the command
            result = subprocess.run(
                instruction,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=30  # 30 second timeout
            )
            
            # Combine stdout and stderr for complete output
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            output += f"Return code: {result.returncode}"
            
            return output, None
            
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after 30 seconds: {instruction}"
            _logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Error executing command '{instruction}': {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def validate_result(self, result: Any) -> bool:
        """Validate bash execution result."""
        return result is not None and isinstance(result, str)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform bash output to artifact."""
        return Artefact(
            id=artifact_id,
            type="text",
            code=result,  # Use 'code' field for text content
            description=f"Output from bash command: {instruction[:50]}..."
        )