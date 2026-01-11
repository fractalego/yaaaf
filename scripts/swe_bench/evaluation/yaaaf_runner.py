"""
Runs YAAAF on a SWE-bench instance via the HTTP API (same as CLI).

Requires the YAAAF backend to be running:
    python -m yaaaf backend 4000
"""

import json
import logging
import uuid
from typing import Optional, List

import httpx

_logger = logging.getLogger(__name__)


class YaaafRunner:
    """Runs YAAAF to solve SWE-bench instances via HTTP API."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4000,
        timeout: int = 600,
    ):
        """Initialize the YAAAF runner.

        Args:
            host: YAAAF backend host
            port: YAAAF backend port
            timeout: Request timeout in seconds
        """
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        # Conversation history for multi-turn dialogue
        self._conversation_history: List[dict] = []

    def check_server(self) -> bool:
        """Check if the YAAAF backend is running.

        Returns:
            True if server is reachable
        """
        try:
            response = httpx.get(
                f"{self.base_url}/get_agents_config",
                timeout=5.0
            )
            if response.status_code == 200:
                config = response.json()
                # Response is a list of {"name": ..., "type": ...} items
                if isinstance(config, list):
                    agents = [a.get("name") for a in config if a.get("type") == "agent"]
                else:
                    agents = [a.get("name") for a in config.get("agents", [])]
                _logger.info(f"YAAAF server available. Agents: {agents}")
                return True
        except httpx.ConnectError:
            _logger.error(f"Cannot connect to YAAAF server at {self.base_url}")
            _logger.error("Start the backend: python -m yaaaf backend 4000")
        except Exception as e:
            _logger.error(f"Error checking server: {e}")
        return False

    def build_prompt(
        self,
        problem_statement: str,
        repo_path: str,
        hints: Optional[str] = None,
        fail_to_pass: Optional[List[str]] = None,
        pass_to_pass: Optional[List[str]] = None,
    ) -> str:
        """Build a prompt for YAAAF from a SWE-bench instance.

        Args:
            problem_statement: The GitHub issue description
            repo_path: Path to the repository
            hints: Optional hints from issue comments
            fail_to_pass: List of test names that should pass after the fix
            pass_to_pass: List of test names that must not regress

        Returns:
            Formatted prompt for YAAAF
        """
        prompt = f"""You are a software engineer tasked with fixing a bug in a Python repository.

## Repository Location
The repository is located at: {repo_path}

## Problem Description
{problem_statement}
"""

        if hints:
            prompt += f"""
## Additional Context (from issue comments)
{hints}
"""

        # Add test information - this is critical for the agent to know what to fix
        if fail_to_pass:
            prompt += f"""
## Tests That Must Pass After Your Fix
The following tests currently FAIL and must PASS after your fix:
"""
            for test in fail_to_pass:
                prompt += f"- `{test}`\n"
            prompt += """
These test names indicate exactly what functionality needs to be fixed.
You may need to add new test cases to the test file with these specific parameter names.
"""

        if pass_to_pass:
            prompt += f"""
## Tests That Must Not Regress
The following tests currently pass and must continue to pass (sample of {len(pass_to_pass)} tests):
"""
            for test in pass_to_pass[:5]:  # Show first 5 only
                prompt += f"- `{test}`\n"
            if len(pass_to_pass) > 5:
                prompt += f"- ... and {len(pass_to_pass) - 5} more\n"

        prompt += """
## Instructions
1. First, explore the repository to understand its structure
2. Find the relevant files mentioned in the issue
3. Understand the bug by reading the code
4. Implement a fix using code editing
5. Run the specific failing tests to verify your fix works
6. Ensure you don't break existing tests

Use the available tools:
- BashAgent: For exploring files (find, grep, ls, cat) and running tests (pytest)
- CodeEditAgent: For viewing and modifying source files

Focus on making minimal, targeted changes to fix the issue.
"""

        return prompt

    def reset_conversation(self):
        """Reset the conversation history for a new instance."""
        self._conversation_history = []

    def build_feedback_message(
        self,
        test_output: str,
        test_passed: int,
        test_failed: int,
        test_errors: int,
        attempt: int,
        max_attempts: int,
    ) -> str:
        """Build a feedback message based on test results.

        Args:
            test_output: Raw output from pytest
            test_passed: Number of passed tests
            test_failed: Number of failed tests
            test_errors: Number of test errors
            attempt: Current attempt number
            max_attempts: Maximum number of attempts

        Returns:
            Formatted feedback message
        """
        remaining = max_attempts - attempt

        feedback = f"""## Test Results After Your Changes (Attempt {attempt}/{max_attempts})

The tests did not pass. Here are the results:
- Passed: {test_passed}
- Failed: {test_failed}
- Errors: {test_errors}

### Test Output
```
{test_output[-3000:] if len(test_output) > 3000 else test_output}
```

### What to do next
You have {remaining} attempt(s) remaining. Please:
1. Analyze the error messages above carefully
2. Identify what went wrong with your previous fix
3. Make the necessary corrections

Common issues to check:
- Did you modify the correct file?
- Did you add the required test cases to the test file?
- Did your changes break any existing functionality?
- Are there syntax errors in your changes?

Please try again with a corrected approach.
"""
        return feedback

    def run(
        self,
        problem_statement: str,
        repo_path: str,
        hints: Optional[str] = None,
        env_path: Optional[str] = None,
        fail_to_pass: Optional[List[str]] = None,
        pass_to_pass: Optional[List[str]] = None,
    ) -> dict:
        """Run YAAAF on a problem instance (first turn of conversation).

        Args:
            problem_statement: The GitHub issue description
            repo_path: Path to the repository
            hints: Optional hints from issue comments
            env_path: Optional path to Python virtual environment (for running tests)
            fail_to_pass: List of test names that should pass after the fix
            pass_to_pass: List of test names that must not regress

        Returns:
            Dict with 'success', 'response', 'prompt'
        """
        # Reset conversation for new instance
        self.reset_conversation()

        # Check server first
        if not self.check_server():
            return {
                "success": False,
                "response": "YAAAF server not available",
                "prompt": "",
            }

        # Build the prompt
        prompt = self.build_prompt(problem_statement, repo_path, hints, fail_to_pass, pass_to_pass)

        # Store env_path and repo_path for subsequent turns
        self._env_path = env_path
        self._working_dir = repo_path  # Use repo_path as working directory for file operations

        # Add to conversation history
        self._conversation_history.append({"role": "user", "content": prompt})

        # Send conversation
        return self._send_conversation(prompt)

    def continue_with_feedback(self, feedback: str) -> dict:
        """Continue the conversation with feedback about test results.

        Args:
            feedback: Feedback message about test failures

        Returns:
            Dict with 'success', 'response', 'prompt'
        """
        if not self._conversation_history:
            return {
                "success": False,
                "response": "No conversation to continue",
                "prompt": feedback,
            }

        # Check server
        if not self.check_server():
            return {
                "success": False,
                "response": "YAAAF server not available",
                "prompt": feedback,
            }

        # Add assistant's previous response (summarized) and new user feedback
        # Note: We don't have the full assistant response stored, so we just add the feedback
        self._conversation_history.append({"role": "user", "content": feedback})

        return self._send_conversation(feedback)

    def _send_conversation(self, latest_prompt: str) -> dict:
        """Send the current conversation to YAAAF.

        Args:
            latest_prompt: The latest prompt (for logging/return purposes)

        Returns:
            Dict with 'success', 'response', 'prompt'
        """
        stream_id = f"eval_{uuid.uuid4().hex[:8]}"

        try:
            # Create stream with full conversation history
            _logger.info(f"Sending conversation ({len(self._conversation_history)} messages) to YAAAF...")
            request_body = {
                "stream_id": stream_id,
                "messages": self._conversation_history,
            }
            if hasattr(self, '_env_path') and self._env_path:
                request_body["env_path"] = self._env_path
                _logger.info(f"Using environment: {self._env_path}")
            if hasattr(self, '_working_dir') and self._working_dir:
                request_body["working_dir"] = self._working_dir
                _logger.info(f"Using working directory: {self._working_dir}")

            create_resp = httpx.post(
                f"{self.base_url}/create_stream",
                json=request_body,
                timeout=10.0,
            )

            if create_resp.status_code != 200:
                return {
                    "success": False,
                    "response": f"Server returned {create_resp.status_code}",
                    "prompt": latest_prompt,
                }

            # Stream the response
            response = self._stream_response(stream_id)

            return {
                "success": True,
                "response": response,
                "prompt": latest_prompt,
            }

        except httpx.RequestError as e:
            _logger.error(f"Request failed: {e}")
            return {
                "success": False,
                "response": str(e),
                "prompt": latest_prompt,
            }
        except Exception as e:
            _logger.error(f"YAAAF execution failed: {e}")
            return {
                "success": False,
                "response": str(e),
                "prompt": latest_prompt,
            }

    def _stream_response(self, stream_id: str) -> str:
        """Stream the response from YAAAF.

        Args:
            stream_id: The stream ID to read from

        Returns:
            Collected response text
        """
        collected_messages = []
        artifact_ids = []

        try:
            _logger.info(f"Starting stream for {stream_id} (timeout={self.timeout}s)")
            with httpx.stream(
                "POST",
                f"{self.base_url}/stream_utterances",
                json={"stream_id": stream_id},
                timeout=httpx.Timeout(float(self.timeout), connect=10.0),
            ) as response:
                _logger.info(f"Stream connected, status={response.status_code}")
                buffer = ""
                chunk_count = 0
                for chunk in response.iter_text():
                    chunk_count += 1
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str:
                                try:
                                    note = json.loads(data_str)
                                    result = self._process_note(note)
                                    if result:
                                        collected_messages.append(result)
                                        _logger.debug(f"Note: {result[:100]}...")
                                    if note.get("artefact_id"):
                                        artifact_ids.append(note["artefact_id"])
                                except json.JSONDecodeError:
                                    pass

            _logger.info(f"Stream ended after {chunk_count} chunks, {len(collected_messages)} messages")

        except httpx.ReadTimeout:
            collected_messages.append("[Timeout waiting for response]")
            _logger.warning("Response timed out")
        except Exception as e:
            collected_messages.append(f"[Stream error: {e}]")
            _logger.error(f"Stream error: {e}", exc_info=True)

        # Fetch artifacts
        for artifact_id in artifact_ids:
            artifact_content = self._fetch_artifact(artifact_id)
            if artifact_content:
                collected_messages.append(artifact_content)

        return "\n".join(collected_messages) if collected_messages else "[No response]"

    def _process_note(self, note: dict) -> Optional[str]:
        """Process a single note from the stream."""
        message = note.get("message", "")
        is_internal = note.get("internal", False)
        is_status = note.get("is_status", False)
        agent_name = note.get("agent_name", "")

        # Skip internal messages
        if is_internal:
            return None

        # Skip empty messages
        if not message or not message.strip():
            return None

        # Skip completion markers
        if message.strip().lower() in ("taskcompleted", "taskpaused"):
            return None

        # Format status messages
        if is_status:
            return f"[{agent_name}] {message}" if agent_name else f"[Status] {message}"

        return message

    def _fetch_artifact(self, artifact_id: str) -> Optional[str]:
        """Fetch and format an artifact."""
        try:
            resp = httpx.post(
                f"{self.base_url}/get_artefact",
                json={"artefact_id": artifact_id},
                timeout=30.0,
            )
            if resp.status_code == 200:
                artifact = resp.json()
                parts = []

                summary = artifact.get("summary", "").strip()
                if summary:
                    parts.append(summary)

                code = artifact.get("code", "").strip()
                if code:
                    parts.append(f"\n```\n{code}\n```")

                return "\n".join(parts) if parts else None
        except Exception as e:
            _logger.warning(f"Failed to fetch artifact {artifact_id}: {e}")
        return None


def test_runner():
    """Simple test of the runner."""
    logging.basicConfig(level=logging.INFO)

    runner = YaaafRunner()

    if not runner.check_server():
        print("Server not running. Start with: python -m yaaaf backend 4000")
        return

    result = runner.run(
        problem_statement="List all Python files in the current directory",
        repo_path="/tmp",
    )

    print(f"Success: {result['success']}")
    print(f"Response: {result['response'][:500]}...")


if __name__ == "__main__":
    test_runner()
