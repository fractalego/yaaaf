"""
Runs YAAAF on a SWE-bench instance via the HTTP API (same as CLI).

Requires the YAAAF backend to be running:
    python -m yaaaf backend 4000
"""

import json
import logging
import uuid
from typing import Optional

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
        hints: Optional[str] = None
    ) -> str:
        """Build a prompt for YAAAF from a SWE-bench instance.

        Args:
            problem_statement: The GitHub issue description
            repo_path: Path to the repository
            hints: Optional hints from issue comments

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

        prompt += """
## Instructions
1. First, explore the repository to understand its structure
2. Find the relevant files mentioned in the issue
3. Understand the bug by reading the code
4. Implement a fix using code editing
5. Verify your changes make sense

Use the available tools:
- BashAgent: For exploring files (find, grep, ls, cat)
- CodeEditAgent: For viewing and modifying source files

Focus on making minimal, targeted changes to fix the issue.
"""

        return prompt

    def run(
        self,
        problem_statement: str,
        repo_path: str,
        hints: Optional[str] = None,
    ) -> dict:
        """Run YAAAF on a problem instance.

        Args:
            problem_statement: The GitHub issue description
            repo_path: Path to the repository
            hints: Optional hints from issue comments

        Returns:
            Dict with 'success', 'response', 'prompt'
        """
        # Check server first
        if not self.check_server():
            return {
                "success": False,
                "response": "YAAAF server not available",
                "prompt": "",
            }

        # Build the prompt
        prompt = self.build_prompt(problem_statement, repo_path, hints)

        # Create conversation
        messages = [{"role": "user", "content": prompt}]
        stream_id = f"eval_{uuid.uuid4().hex[:8]}"

        try:
            # Create stream
            _logger.info("Sending query to YAAAF...")
            create_resp = httpx.post(
                f"{self.base_url}/create_stream",
                json={"stream_id": stream_id, "messages": messages},
                timeout=10.0,
            )

            if create_resp.status_code != 200:
                return {
                    "success": False,
                    "response": f"Server returned {create_resp.status_code}",
                    "prompt": prompt,
                }

            # Stream the response
            response = self._stream_response(stream_id)

            return {
                "success": True,
                "response": response,
                "prompt": prompt,
            }

        except httpx.RequestError as e:
            _logger.error(f"Request failed: {e}")
            return {
                "success": False,
                "response": str(e),
                "prompt": prompt,
            }
        except Exception as e:
            _logger.error(f"YAAAF execution failed: {e}")
            return {
                "success": False,
                "response": str(e),
                "prompt": prompt,
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
            with httpx.stream(
                "POST",
                f"{self.base_url}/stream_utterances",
                json={"stream_id": stream_id},
                timeout=httpx.Timeout(float(self.timeout), connect=10.0),
            ) as response:
                buffer = ""
                for chunk in response.iter_text():
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

        except httpx.ReadTimeout:
            collected_messages.append("[Timeout waiting for response]")
            _logger.warning("Response timed out")
        except Exception as e:
            collected_messages.append(f"[Stream error: {e}]")
            _logger.error(f"Stream error: {e}")

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
