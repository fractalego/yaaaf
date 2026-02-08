import logging
import asyncio
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

    def __init__(self, skip_safety_check: bool = False):
        """Initialize bash executor.

        Args:
            skip_safety_check: If True, skip safety checks and allow all commands
        """
        self._storage = ArtefactStorage()
        self._skip_safety_check = skip_safety_check
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for bash execution with artifact resolution."""
        context = await super().prepare_context(messages, notes)
        context["working_dir"] = os.getcwd()
        return context

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract bash command from response."""
        command = get_first_text_between_tags(response, "```bash", "```")
        if not command:
            _logger.debug(f"No ```bash block found in response: {response[:200]}...")
            return None

        # ALWAYS check for interactive commands (they will hang execution)
        interactive_commands = ["nano ", "vim ", "vi ", "emacs ", "less ", "more ", "pico "]
        command_lower = command.strip().lower()
        for cmd in interactive_commands:
            if command_lower.startswith(cmd) or f"\n{cmd}" in command_lower:
                _logger.error(f"BLOCKED interactive command: {cmd.strip()}")
                _logger.error(f"Interactive commands hang execution. Use 'cat' to view files, not {cmd.strip()}")
                return None

        # Other safety checks (can be skipped if needed)
        if not self._skip_safety_check and not self._is_safe_command(command):
            _logger.warning(f"Command rejected as unsafe: {command}")
            return None
        _logger.info(f"Extracted bash command: {command}")
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

        # Interactive commands that would hang
        interactive_commands = ["nano ", "vim ", "vi ", "emacs ", "less ", "more ", "pico "]
        for cmd in interactive_commands:
            if command.strip().startswith(cmd) or f"\n{cmd}" in command:
                _logger.warning(f"Blocked interactive command: {cmd.strip()}")
                return False
        
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
        """Execute bash command asynchronously (non-blocking)."""
        try:
            # Change to working directory if specified
            working_dir = context.get("working_dir", os.getcwd())
            _logger.info(f"Bash executing in working_dir: {working_dir}")

            # Set up environment with optional virtual environment PATH
            env = os.environ.copy()
            env_path = context.get("env_path")
            if env_path:
                # Prepend venv bin directory to PATH so tools like pytest are found
                env["PATH"] = f"{env_path}/bin:{env['PATH']}"
                env["VIRTUAL_ENV"] = env_path
                _logger.info(f"Using virtual environment: {env_path}")

                # Check if we need to use PYTHONPATH fallback (for packages where editable install failed)
                import pathlib
                use_pythonpath_marker = pathlib.Path(env_path) / ".use_pythonpath"
                pythonpath_set = False
                if use_pythonpath_marker.exists() and working_dir:
                    existing_pythonpath = env.get("PYTHONPATH", "")
                    env["PYTHONPATH"] = f"{working_dir}:{existing_pythonpath}" if existing_pythonpath else working_dir
                    _logger.info(f"Using PYTHONPATH fallback: {env['PYTHONPATH']}")
                    pythonpath_set = True

                # Django-specific: Always use PYTHONPATH to prioritize repo code over site-packages
                # This is critical because Django's test runner imports from django.utils.deprecation
                # which may have different classes in different Django versions (e.g., RemovedInDjango40Warning)
                if working_dir and "django" in working_dir.lower() and not pythonpath_set:
                    existing_pythonpath = env.get("PYTHONPATH", "")
                    env["PYTHONPATH"] = f"{working_dir}:{existing_pythonpath}" if existing_pythonpath else working_dir
                    _logger.info(f"Django detected - setting PYTHONPATH to prioritize repo: {env['PYTHONPATH']}")

                # Django-specific: Set minimal settings for pytest-django
                if working_dir and "django" in working_dir.lower():
                    # pytest-django requires a valid Django settings module
                    # Try to find the test settings in common locations
                    if "DJANGO_SETTINGS_MODULE" not in env:
                        import pathlib
                        work_path = pathlib.Path(working_dir)

                        # Common Django test settings patterns
                        test_settings_candidates = [
                            "tests.test_sqlite",      # Most common in Django repo
                            "test_sqlite",            # Alternative
                            "tests.settings",         # Generic test settings
                            "django.conf.settings",   # Main Django settings
                        ]

                        # Check if any of these modules exist
                        found_settings = None
                        for candidate in test_settings_candidates:
                            # Convert module path to file path (e.g., tests.test_sqlite -> tests/test_sqlite.py)
                            module_file = candidate.replace(".", "/") + ".py"
                            if (work_path / module_file).exists():
                                found_settings = candidate
                                _logger.info(f"Found Django test settings: {found_settings}")
                                break

                        if found_settings:
                            env["DJANGO_SETTINGS_MODULE"] = found_settings
                        else:
                            # Fallback: create minimal settings on the fly
                            # Don't use global_settings - it's not a valid settings module
                            # Instead, let pytest-django fail gracefully or skip Django setup
                            _logger.warning("No Django test settings found, pytest-django may fail")
                            env["DJANGO_SETTINGS_MODULE"] = "tests.test_sqlite"  # Try anyway

                        _logger.info(f"Set DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")
                    # Disable Django debug mode for tests
                    env["DJANGO_DEBUG"] = "False"

            # Execute the command asynchronously to avoid blocking the event loop
            process = await asyncio.create_subprocess_shell(
                instruction,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

            # Determine timeout based on command type
            # Django tests need much longer (database setup + test execution)
            # pytest can also take a while with many tests
            if "runtests.py" in instruction or "pytest" in instruction or "python -m pytest" in instruction:
                timeout = 300  # 5 minutes for test runs
                _logger.info(f"Test command detected - using extended timeout: {timeout}s")
            else:
                timeout = 60  # 1 minute for regular commands (increased from 30s)

            try:
                _logger.info(f"Waiting for command to complete (timeout={timeout}s)...")
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                _logger.info(f"Command completed with return code: {process.returncode}")
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error_msg = f"Command timed out after {timeout} seconds: {instruction}"
                _logger.error(error_msg)
                return None, error_msg

            # Combine stdout and stderr for complete output
            output = ""
            if stdout:
                output += f"STDOUT:\n{stdout.decode('utf-8', errors='replace')}\n"
            if stderr:
                output += f"STDERR:\n{stderr.decode('utf-8', errors='replace')}\n"
            output += f"Return code: {process.returncode}"

            # If command failed, return as error so reflection pattern can retry
            if process.returncode != 0:
                return None, f"Command failed with exit code {process.returncode}:\n{output}"

            return output, None

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