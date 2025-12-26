import logging
import os
import re
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class CodeEditExecutor(ToolExecutor):
    """Executor for code editing operations.

    Supports three operations:
    - view: Read file contents with line numbers
    - create: Create new files with content
    - str_replace: Replace exact strings in files

    This executor mimics the str_replace_editor tool used in SWE-bench.
    """

    def __init__(self, allowed_directories: Optional[list[str]] = None):
        """Initialize code edit executor.

        Args:
            allowed_directories: List of directories where editing is allowed.
                                If None, defaults to current working directory.
        """
        self._storage = ArtefactStorage()
        self._allowed_directories = allowed_directories or [os.getcwd()]

    def _is_path_allowed(self, file_path: str) -> bool:
        """Check if the file path is within allowed directories."""
        abs_path = os.path.abspath(file_path)
        for allowed_dir in self._allowed_directories:
            abs_allowed = os.path.abspath(allowed_dir)
            if abs_path.startswith(abs_allowed):
                return True
        return False

    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for code editing."""
        return {
            "messages": messages,
            "notes": notes or [],
            "working_dir": os.getcwd(),
            "allowed_directories": self._allowed_directories
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract code edit instruction from response.

        Expected format:
        ```code_edit
        operation: view|create|str_replace
        path: /path/to/file
        content: (for create)
        old_str: (for str_replace)
        new_str: (for str_replace)
        ```
        """
        # Try to find code_edit block
        pattern = r"```code_edit\s*(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            instruction = match.group(1).strip()
            _logger.info(f"Extracted code_edit instruction: {instruction[:100]}...")
            return instruction

        _logger.info(f"No ```code_edit block found in response: {response[:200]}...")
        return None

    def _parse_instruction(self, instruction: str) -> Dict[str, str]:
        """Parse the instruction into operation and parameters."""
        result = {}
        current_key = None
        current_value = []

        for line in instruction.split('\n'):
            # Check if this is a new key
            if ':' in line and not line.startswith(' ') and not line.startswith('\t'):
                # Save previous key if exists
                if current_key:
                    result[current_key] = '\n'.join(current_value).strip()

                key, _, value = line.partition(':')
                current_key = key.strip().lower()
                current_value = [value.strip()] if value.strip() else []
            elif current_key:
                # Continuation of previous value
                current_value.append(line)

        # Save last key
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()

        return result

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Execute code edit operation."""
        try:
            params = self._parse_instruction(instruction)
            operation = params.get('operation', '').lower()
            file_path = params.get('path', '')

            if not file_path:
                return None, "No file path specified"

            # Resolve path relative to working directory if not absolute
            if not os.path.isabs(file_path):
                file_path = os.path.join(context.get("working_dir", os.getcwd()), file_path)

            # Security check
            if not self._is_path_allowed(file_path):
                return None, f"Path not allowed: {file_path}. Allowed directories: {self._allowed_directories}"

            if operation == 'view':
                return self._view_file(file_path, params)
            elif operation == 'create':
                return self._create_file(file_path, params)
            elif operation == 'str_replace':
                return self._str_replace(file_path, params)
            else:
                _logger.warning(f"Invalid operation '{operation}' requested. Only view/create/str_replace are supported.")
                return None, (
                    f"INVALID OPERATION: '{operation}' is not supported. "
                    f"This agent ONLY supports: 'view', 'create', or 'str_replace'. "
                    f"To FIX code, use 'str_replace' with old_str and new_str to replace the buggy code. "
                    f"Do NOT try to use bash commands here - use the bash agent for that."
                )

        except Exception as e:
            error_msg = f"Error executing code edit: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def _view_file(self, file_path: str, params: Dict[str, str]) -> Tuple[Any, Optional[str]]:
        """View file contents with line numbers."""
        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Optional line range
            start_line = int(params.get('start_line', 1))
            end_line = int(params.get('end_line', len(lines)))

            # Build output with line numbers
            output_lines = []
            for i, line in enumerate(lines[start_line-1:end_line], start=start_line):
                output_lines.append(f"{i:6d}\t{line.rstrip()}")

            result = f"File: {file_path}\n"
            result += f"Lines: {start_line}-{min(end_line, len(lines))} of {len(lines)}\n"
            result += "-" * 60 + "\n"
            result += "\n".join(output_lines)

            return result, None

        except UnicodeDecodeError:
            return None, f"Cannot read file as text: {file_path}"
        except Exception as e:
            return None, f"Error reading file: {str(e)}"

    def _create_file(self, file_path: str, params: Dict[str, str]) -> Tuple[Any, Optional[str]]:
        """Create a new file with content."""
        content = params.get('content', '')

        if not content:
            return None, "No content specified for file creation"

        # Check if file already exists
        if os.path.exists(file_path):
            return None, f"File already exists: {file_path}. Use str_replace to modify it."

        try:
            # Create parent directories if needed
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            line_count = content.count('\n') + 1
            result = f"Created file: {file_path}\n"
            result += f"Lines written: {line_count}\n"
            result += f"Size: {len(content)} bytes"

            return result, None

        except Exception as e:
            return None, f"Error creating file: {str(e)}"

    def _str_replace(self, file_path: str, params: Dict[str, str]) -> Tuple[Any, Optional[str]]:
        """Replace exact string in file."""
        old_str = params.get('old_str', '')
        new_str = params.get('new_str', '')

        if not old_str:
            return None, "No old_str specified for replacement"

        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if old_str exists
            if old_str not in content:
                # Try to find similar matches for helpful error message
                lines_with_partial = []
                for i, line in enumerate(content.split('\n'), 1):
                    if any(word in line for word in old_str.split()[:3]):
                        lines_with_partial.append(f"  Line {i}: {line[:100]}...")

                error_msg = f"String not found in file: {file_path}\n"
                if lines_with_partial:
                    error_msg += "Similar lines found:\n" + "\n".join(lines_with_partial[:5])
                return None, error_msg

            # Count occurrences
            count = content.count(old_str)
            if count > 1:
                return None, f"String found {count} times in file. Please provide more context to make the match unique."

            # Perform replacement
            new_content = content.replace(old_str, new_str, 1)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Calculate what changed
            old_lines = old_str.count('\n') + 1
            new_lines = new_str.count('\n') + 1

            result = f"Replaced in file: {file_path}\n"
            result += f"Removed: {old_lines} lines ({len(old_str)} chars)\n"
            result += f"Added: {new_lines} lines ({len(new_str)} chars)"

            return result, None

        except UnicodeDecodeError:
            return None, f"Cannot read file as text: {file_path}"
        except Exception as e:
            return None, f"Error replacing string: {str(e)}"

    def validate_result(self, result: Any) -> bool:
        """Validate code edit result."""
        return result is not None and isinstance(result, str)

    def get_feedback_message(self, error: str) -> str:
        """Provide detailed feedback for code edit errors."""
        if "INVALID OPERATION" in error:
            return (
                f"{error}\n\n"
                "EXAMPLE of str_replace to fix code:\n"
                "```code_edit\n"
                "operation: str_replace\n"
                "path: /path/to/file.py\n"
                "old_str:\n"
                "def buggy_function():\n"
                "    return wrong_value\n"
                "new_str:\n"
                "def buggy_function():\n"
                "    return correct_value\n"
                "```"
            )
        return f"Error: {error}. Please correct and try again."

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform code edit result to artifact."""
        # Extract operation type from instruction for description
        params = self._parse_instruction(instruction)
        operation = params.get('operation', 'edit')
        file_path = params.get('path', 'unknown')

        return Artefact(
            id=artifact_id,
            type="text",
            code=result,
            description=f"Code edit ({operation}) on: {os.path.basename(file_path)}"
        )
