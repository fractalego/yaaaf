import logging
import os
import re
import asyncio
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class CodeEditExecutor(ToolExecutor):
    """Executor for code editing operations.

    Supports four operations:
    - view: Read file contents with line numbers
    - create: Create new files with content
    - str_replace: Replace exact strings in files
    - bash: Execute shell commands

    This executor mimics the str_replace_editor tool used in SWE-bench with additional bash support.
    """

    def __init__(self, allowed_directories: Optional[list[str]] = None, allow_overwrite: bool = True):
        """Initialize code edit executor.

        Args:
            allowed_directories: List of directories where editing is allowed.
                                If None, defaults to current working directory.
            allow_overwrite: If True, the 'create' operation can overwrite existing files.
                            Defaults to True for convenience. Set to False for safer behavior.
        """
        self._storage = ArtefactStorage()
        self._allowed_directories = allowed_directories or [os.getcwd()]
        self._allow_overwrite = allow_overwrite
        # Track executed instructions to prevent redundant operations
        self._executed_instructions: Dict[str, Tuple[Any, int]] = {}  # instruction -> (result, step_number)
        self._step_counter = 0

    def _is_path_allowed(self, file_path: str) -> bool:
        """Check if the file path is within allowed directories."""
        return self._is_path_allowed_in(file_path, self._allowed_directories)

    def _is_path_allowed_in(self, file_path: str, allowed_dirs: list) -> bool:
        """Check if the file path is within any of the specified directories."""
        abs_path = os.path.abspath(file_path)
        for allowed_dir in allowed_dirs:
            if allowed_dir:
                abs_allowed = os.path.abspath(allowed_dir)
                if abs_path.startswith(abs_allowed):
                    return True
        return False

    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for code editing with artifact resolution.

        Note: working_dir is set by base_agent from the working_dir parameter passed to query().
        If not set, defaults to os.getcwd().
        """
        context = await super().prepare_context(messages, notes)
        # working_dir may be overridden by base_agent if passed to query()
        if "working_dir" not in context:
            context["working_dir"] = os.getcwd()
        context["allowed_directories"] = self._allowed_directories
        return context

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract code edit instruction from response.

        Supports two formats:
        1. Markdown code blocks (for qwen and similar models):
           ```code_edit
           operation: view|create|str_replace|bash
           path: /path/to/file
           ```
           Or for bash:
           ```code_edit
           operation: bash
           command: your_bash_command
           ```

        2. Tool calls format (for devstral/mistral models):
           [TOOL_CALLS]code_edit
           operation: view|create|str_replace|bash
           path: /path/to/file
           [/TOOL_CALLS]
        """
        # Try markdown code block format first
        pattern = r"```code_edit\s*(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            instruction = match.group(1).strip()
            _logger.info(f"Extracted code_edit instruction:\n{instruction}")
            return instruction

        # Try [TOOL_CALLS] format (devstral/mistral)
        tool_pattern = r"\[TOOL_CALLS\]code_edit\s*(.*?)(?:\[/TOOL_CALLS\]|$)"
        match = re.search(tool_pattern, response, re.DOTALL)
        if match:
            instruction = match.group(1).strip()
            _logger.info(f"Extracted code_edit instruction (TOOL_CALLS format):\n{instruction}")
            return instruction

        # Try variant without closing tag (model might not include it)
        tool_pattern_open = r"\[TOOL_CALLS\]code_edit\s*(operation:.*?)(?:\[TOOL_CALLS\]|\[/TOOL_CALLS\]|$)"
        match = re.search(tool_pattern_open, response, re.DOTALL)
        if match:
            instruction = match.group(1).strip()
            _logger.info(f"Extracted code_edit instruction (TOOL_CALLS open format):\n{instruction}")
            return instruction

        # Check if model is trying to use wrong tool
        if "[TOOL_CALLS]bash" in response:
            _logger.warning("Model tried to use bash - not allowed in code_edit agent")
            return "operation: invalid_bash_attempt"

        # Check if model is outputting JSON format (e.g., nemotron with "thoughts")
        if '"thoughts"' in response or '{"' in response:
            _logger.warning("Model using JSON format instead of code_edit block")
            return "operation: invalid_json_format"

        _logger.info(f"No code_edit block found in response: {response[:200]}...")
        return None

    # Known keys for code_edit instructions
    KNOWN_KEYS = {'operation', 'path', 'old_str', 'new_str', 'content', 'start_line', 'end_line', 'command'}

    def _parse_instruction(self, instruction: str) -> Dict[str, str]:
        """Parse the instruction into operation and parameters."""
        result = {}
        current_key = None
        current_value = []

        for line in instruction.split('\n'):
            # Check if this is a new key (must be a known key name)
            if ':' in line and not line.startswith(' ') and not line.startswith('\t'):
                key_candidate = line.partition(':')[0].strip().lower()
                if key_candidate in self.KNOWN_KEYS:
                    # Save previous key if exists
                    if current_key:
                        result[current_key] = '\n'.join(current_value).strip()

                    key, _, value = line.partition(':')
                    current_key = key.strip().lower()
                    current_value = [value.strip()] if value.strip() else []
                elif current_key:
                    # Not a known key, treat as continuation of previous value
                    current_value.append(line)
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
            # Increment step counter
            self._step_counter += 1

            params = self._parse_instruction(instruction)
            operation = params.get('operation', '').lower()

            # Handle case where model outputs JSON instead of code_edit block
            if operation == 'invalid_json_format':
                return None, (
                    "WRONG FORMAT: Do NOT output JSON. You MUST use the code_edit block format.\n\n"
                    "CORRECT FORMAT:\n"
                    "```code_edit\n"
                    "operation: view\n"
                    "path: /path/to/file.py\n"
                    "```\n\n"
                    "Or for editing:\n"
                    "```code_edit\n"
                    "operation: str_replace\n"
                    "path: /path/to/file.py\n"
                    "old_str:\n"
                    "<exact text from file>\n"
                    "new_str:\n"
                    "<your fixed version>\n"
                    "```\n\n"
                    "Or for bash commands:\n"
                    "```code_edit\n"
                    "operation: bash\n"
                    "command: pytest tests/test_file.py\n"
                    "```\n\n"
                    "DO NOT use JSON. Use the ```code_edit block exactly as shown above."
                )

            # Check for valid operation BEFORE checking path
            if operation not in ('view', 'create', 'str_replace', 'bash'):
                _logger.warning(f"Invalid operation '{operation}' requested. Only view/create/str_replace/bash are supported.")
                return None, (
                    f"INVALID OPERATION: '{operation}' is not supported. "
                    f"This agent ONLY supports: 'view', 'create', 'str_replace', or 'bash'. "
                    f"To FIX code, use 'str_replace' with old_str and new_str to replace the buggy code."
                )

            # Handle bash operation separately (doesn't need file path)
            if operation == 'bash':
                return await self._execute_bash(params, context)

            file_path = params.get('path', '')

            if not file_path:
                return None, "No file path specified"

            # Resolve path relative to working directory if not absolute
            if not os.path.isabs(file_path):
                working_dir = context.get("working_dir", os.getcwd())
                _logger.info(f"Resolving relative path '{file_path}' against working_dir: {working_dir}")
                file_path = os.path.join(working_dir, file_path)

            # Security check - allow paths within working_dir OR allowed_directories
            working_dir = context.get("working_dir", self._allowed_directories[0] if self._allowed_directories else os.getcwd())
            allowed_dirs = list(self._allowed_directories) + ([working_dir] if working_dir else [])
            if not self._is_path_allowed_in(file_path, allowed_dirs):
                return None, (
                    f"Path not allowed: {file_path}\n"
                    f"You MUST use paths starting with: {working_dir}\n"
                    f"Check spelling carefully - do NOT change the directory names!"
                )

            # Check if this view operation was already executed (prevent redundant views)
            if operation == 'view':
                # Create a canonical key for this instruction
                instruction_key = instruction.strip()
                if instruction_key in self._executed_instructions:
                    cached_result, previous_step = self._executed_instructions[instruction_key]
                    warning_msg = (
                        f"⚠️ Note: You already viewed this file in step {previous_step} of {self._step_counter}. "
                        f"The previous result is shown below.\n\n"
                        f"{cached_result}"
                    )
                    _logger.info(f"Duplicate view operation detected: {instruction_key[:100]}... (from step {previous_step})")
                    return warning_msg, None

            if operation == 'view':
                result, error = self._view_file(file_path, params)
                # Cache successful view operations
                if error is None:
                    self._executed_instructions[instruction.strip()] = (result, self._step_counter)
                return result, error
            elif operation == 'create':
                return self._create_file(file_path, params)
            else:  # str_replace (already validated above)
                return self._str_replace(file_path, params)

        except Exception as e:
            error_msg = f"Error executing code edit: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def _view_file(self, file_path: str, params: Dict[str, str]) -> Tuple[Any, Optional[str]]:
        """View file contents with line numbers."""
        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"

        if os.path.isdir(file_path):
            return None, (
                f"ERROR: '{file_path}' is a directory, not a file. "
                f"You must specify a FILE path, not a directory. "
                f"Example: path: {file_path}/some_file.py"
            )

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
        """Create a new file with content (or overwrite if allow_overwrite=True)."""
        content = params.get('content', '')

        if not content:
            return None, "No content specified for file creation"

        # Check if file already exists
        file_existed = os.path.exists(file_path)
        if file_existed and not self._allow_overwrite:
            return None, f"File already exists: {file_path}. Use str_replace to modify it."

        try:
            # Create parent directories if needed
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            line_count = content.count('\n') + 1
            action = "Overwrote" if file_existed else "Created"
            result = f"{action} file: {file_path}\n"
            result += f"Lines written: {line_count}\n"
            result += f"Size: {len(content)} bytes"

            return result, None

        except Exception as e:
            return None, f"Error creating file: {str(e)}"

    def _parse_numbered_lines(self, text: str) -> Optional[Dict[int, str]]:
        """Parse text with line numbers into a dict of {line_number: content}.

        Detects patterns like "  97:    code" or "   97	code" or "   97   code" at start of lines.
        Returns None if no line numbers detected, otherwise dict mapping line nums to content.
        """
        lines = text.split('\n')
        numbered_lines = {}

        for line in lines:
            # Match patterns like "  97:" or "97:" or "   97\t" or "   97   "
            # (line number followed by colon, tab, or 2+ spaces)
            match = re.match(r'^\s*(\d+)(?::\s?|\t|\s{2,})', line)
            if match:
                line_num = int(match.group(1))
                content = line[match.end():]
                numbered_lines[line_num] = content

        # Only return if we found numbered lines
        return numbered_lines if numbered_lines else None

    def _str_replace(self, file_path: str, params: Dict[str, str]) -> Tuple[Any, Optional[str]]:
        """Replace exact string in file."""
        old_str = params.get('old_str', '')
        new_str = params.get('new_str', '')

        if not old_str:
            return None, "No old_str specified for replacement"

        # Check for empty/malformed new_str - likely due to token limit truncation
        if not new_str or not new_str.strip():
            return None, (
                "ERROR: new_str is EMPTY. Your response was likely TRUNCATED due to token limits.\n\n"
                "To fix this, BE MORE CONCISE:\n"
                "1. Use SMALLER old_str - only include the specific lines you need to change, not entire functions\n"
                "2. Do NOT include line numbers in old_str or new_str\n"
                "3. Make one small, focused change at a time\n"
                "4. If you need to change multiple parts, do them in separate str_replace operations\n\n"
                "Example of a CONCISE replacement:\n"
                "```code_edit\n"
                "operation: str_replace\n"
                "path: /path/to/file.py\n"
                "old_str:\n"
                "    return old_value\n"
                "new_str:\n"
                "    return new_value\n"
                "```"
            )

        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            file_lines = content.split('\n')

            # Check if old_str contains line numbers - if so, use line-based replacement
            old_numbered = self._parse_numbered_lines(old_str)
            new_numbered = self._parse_numbered_lines(new_str)

            # If old_str has line numbers but new_str doesn't, strip line numbers from old_str
            # This handles the common case where the model copies line numbers from view output
            if old_numbered and not new_numbered:
                _logger.info("Detected line numbers in old_str but not new_str - stripping line numbers from old_str")
                # Reconstruct old_str without line numbers
                sorted_lines = sorted(old_numbered.keys())
                old_str = '\n'.join(old_numbered[ln] for ln in sorted_lines)
                _logger.info(f"Stripped old_str (first 200 chars): {old_str[:200]}...")
                # Re-check for numbered lines (should be None now)
                old_numbered = None

            if old_numbered and new_numbered:
                # Line-number based replacement - replace the RANGE of old lines with new lines
                _logger.info(f"Using line-number based replacement for lines: {list(old_numbered.keys())}")

                # Get the range of lines to replace from old_str
                old_line_nums = sorted(old_numbered.keys())
                min_line = min(old_line_nums)
                max_line = max(old_line_nums)

                # Validate range
                if min_line < 1 or max_line > len(file_lines):
                    return None, f"Line range {min_line}-{max_line} is out of range (file has {len(file_lines)} lines)"

                # Get new content lines in order (sorted by line number)
                new_line_nums = sorted(new_numbered.keys())
                new_content_lines = [new_numbered[ln] for ln in new_line_nums]

                # Get the old content before replacing
                old_content_lines = file_lines[min_line - 1:max_line]

                # Replace the range: remove old lines [min_line-1:max_line], insert new lines
                file_lines[min_line - 1:max_line] = new_content_lines

                # Write back
                new_file_content = '\n'.join(file_lines)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_file_content)

                # Build detailed result showing what changed (same format as string-based replacement)
                result = f"str_replace operation completed successfully.\n"
                result += f"File: {file_path}\n"
                result += f"Changed lines {min_line}-{max_line} ({len(old_content_lines)} lines replaced with {len(new_content_lines)} lines)\n\n"
                result += f"BEFORE (old code):\n" + '\n'.join(old_content_lines) + "\n\n"
                result += f"AFTER (new code):\n" + '\n'.join(new_content_lines)
                return result, None

            # Standard string-based replacement
            if old_str not in content:
                # Try to find the function/class the LLM is trying to modify
                first_line = old_str.strip().split('\n')[0].strip()
                error_msg = f"String not found in file: {file_path}\n"
                error_msg += f"You tried to match: {first_line[:80]}...\n\n"

                # Find lines that contain key identifiers from old_str
                for i, line in enumerate(file_lines):
                    if first_line[:30] in line or (len(first_line) > 10 and first_line[4:20] in line):
                        # Show more context around this line (30 lines after)
                        start = max(0, i - 2)
                        end = min(len(file_lines), i + 30)
                        context_lines = file_lines[start:end]
                        error_msg += f"ACTUAL FILE CONTENT (lines {start+1}-{end}):\n"
                        error_msg += "=" * 60 + "\n"
                        for j, ctx_line in enumerate(context_lines, start + 1):
                            error_msg += f"{j:4d}: {ctx_line}\n"
                        error_msg += "=" * 60 + "\n"
                        error_msg += "\nYour old_str did NOT match. Copy the EXACT text from above (including whitespace and docstrings)."
                        return None, error_msg

                # Fallback: show first part of file
                error_msg += "Could not find similar content. First 50 lines of file:\n"
                error_msg += "=" * 60 + "\n"
                for i, line in enumerate(file_lines[:50], 1):
                    error_msg += f"{i:4d}: {line}\n"
                error_msg += "=" * 60 + "\n"
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

            result = f"str_replace operation completed successfully.\n"
            result += f"File: {file_path}\n"
            result += f"Changed {old_lines} lines to {new_lines} lines\n\n"
            result += f"BEFORE (old code):\n{old_str}\n\n"
            result += f"AFTER (new code):\n{new_str}"

            return result, None

        except UnicodeDecodeError:
            return None, f"Cannot read file as text: {file_path}"
        except Exception as e:
            return None, f"Error replacing string: {str(e)}"

    def validate_result(self, result: Any) -> bool:
        """Validate code edit result."""
        return result is not None and isinstance(result, str)

    def is_mutation_operation(self, instruction: str) -> bool:
        """Check if the operation modifies state (vs read-only).

        str_replace, create, and bash are mutations. View is read-only.
        Read-only results are excluded from the final combined artifact.
        """
        params = self._parse_instruction(instruction)
        operation = params.get('operation', '').lower()
        return operation in ('str_replace', 'create', 'bash')

    async def _execute_bash(self, params: Dict[str, str], context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Execute a bash command.

        Args:
            params: Parsed instruction parameters (should contain 'command')
            context: Execution context with working_dir, env_path, etc.

        Returns:
            Tuple of (result, error)
        """
        command = params.get('command', '').strip()

        if not command:
            return None, "No command specified. Use 'command: <your_bash_command>'"

        _logger.info(f"Executing bash command: {command}")

        try:
            # Get working directory and environment
            working_dir = context.get("working_dir", os.getcwd())
            env = os.environ.copy()

            # Set up virtual environment if provided
            env_path = context.get("env_path")
            if env_path:
                env["PATH"] = f"{env_path}/bin:{env['PATH']}"
                env["VIRTUAL_ENV"] = env_path
                _logger.info(f"Using virtual environment: {env_path}")

                # Check for PYTHONPATH fallback marker
                import pathlib
                use_pythonpath_marker = pathlib.Path(env_path) / ".use_pythonpath"
                if use_pythonpath_marker.exists() and working_dir:
                    existing_pythonpath = env.get("PYTHONPATH", "")
                    env["PYTHONPATH"] = f"{working_dir}:{existing_pythonpath}" if existing_pythonpath else working_dir
                    _logger.info(f"Using PYTHONPATH fallback: {env['PYTHONPATH']}")

            # Execute command asynchronously
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

            # Determine timeout based on command type
            # Test runs (Django runtests.py, pytest) need much longer timeouts
            # Database setup + test execution can take several minutes
            if "runtests.py" in command or "pytest" in command or "python -m pytest" in command:
                timeout = 300  # 5 minutes for test runs
                _logger.info(f"Using extended timeout ({timeout}s) for test command")
            else:
                timeout = 60  # 1 minute for regular commands (increased from 30s)

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error_msg = f"Command timed out after {timeout} seconds: {command}"
                _logger.error(error_msg)
                return None, error_msg

            # Combine output
            output = ""
            if stdout:
                output += f"STDOUT:\n{stdout.decode('utf-8', errors='replace')}\n"
            if stderr:
                output += f"STDERR:\n{stderr.decode('utf-8', errors='replace')}\n"
            output += f"Return code: {process.returncode}"

            # If command failed, return as error
            if process.returncode != 0:
                return None, f"Command failed with exit code {process.returncode}:\n{output}"

            return output, None

        except Exception as e:
            error_msg = f"Error executing bash command '{command}': {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

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
                "```\n\n"
                "EXAMPLE of bash command:\n"
                "```code_edit\n"
                "operation: bash\n"
                "command: pytest tests/test_file.py\n"
                "```"
            )
        return f"Error: {error}. Please correct and try again."

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform code edit result to artifact."""
        # Extract operation type from instruction for description
        params = self._parse_instruction(instruction)
        operation = params.get('operation', 'edit')

        # Create description based on operation type
        if operation == 'bash':
            command = params.get('command', 'unknown')
            description = f"Output from bash command: {command[:50]}..."
        else:
            file_path = params.get('path', 'unknown')
            description = f"Code edit ({operation}) on: {os.path.basename(file_path)}"

        return Artefact(
            id=artifact_id,
            type="text",
            code=result,
            description=description
        )
