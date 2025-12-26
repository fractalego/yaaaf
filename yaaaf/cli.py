"""
Simple CLI interface for YAAAF.

Usage:
    python -m yaaaf cli [--host HOST] [--port PORT]
"""

import uuid
import httpx
import json
import sys


def run_cli(host: str = "localhost", port: int = 4000):
    """Run the interactive CLI interface."""
    base_url = f"http://{host}:{port}"

    print(f"YAAAF CLI - Connecting to {base_url}")
    print("Type 'quit' or 'exit' to leave, 'clear' to start a new session.\n")

    # Check server is running
    try:
        response = httpx.get(f"{base_url}/get_agents_config", timeout=5.0)
        if response.status_code == 200:
            config = response.json()
            agents = [a["name"] for a in config.get("agents", [])]
            print(f"Available agents: {', '.join(agents)}")
    except httpx.ConnectError:
        print(f"Error: Cannot connect to server at {base_url}")
        print("Make sure the backend is running: python -m yaaaf backend")
        return
    except Exception as e:
        print(f"Warning: Could not fetch config: {e}")

    print("-" * 50)

    conversation = []
    stream_id = f"cli_{uuid.uuid4().hex[:8]}"

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if user_input.lower() == "clear":
            conversation = []
            stream_id = f"cli_{uuid.uuid4().hex[:8]}"
            print("Session cleared.")
            continue

        # Add user message to conversation
        conversation.append({"role": "user", "content": user_input})

        # Send request
        try:
            response = send_query(base_url, stream_id, conversation)
            if response:
                print(f"\nAssistant: {response}")
                conversation.append({"role": "assistant", "content": response})
        except KeyboardInterrupt:
            print("\n[Interrupted]")
            continue


def send_query(base_url: str, stream_id: str, messages: list) -> str:
    """Send query to the server and stream the response."""
    # Create stream
    create_url = f"{base_url}/create_stream"
    payload = {"stream_id": stream_id, "messages": messages}

    try:
        resp = httpx.post(create_url, json=payload, timeout=10.0)
        if resp.status_code != 200:
            return f"[Error: Server returned {resp.status_code}]"
    except httpx.RequestError as e:
        return f"[Error: {e}]"

    # Stream utterances via SSE
    stream_url = f"{base_url}/stream_utterances"
    collected_messages = []
    artifact_ids = []

    try:
        with httpx.stream(
            "POST",
            stream_url,
            json={"stream_id": stream_id},
            timeout=httpx.Timeout(300.0, connect=10.0),
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
                                result = process_note(note, base_url)
                                if result:
                                    collected_messages.append(result)
                                    # Print progress
                                    sys.stdout.write(".")
                                    sys.stdout.flush()
                                if note.get("artefact_id"):
                                    artifact_ids.append(note["artefact_id"])
                            except json.JSONDecodeError:
                                pass

    except httpx.ReadTimeout:
        collected_messages.append("[Timeout waiting for response]")
    except Exception as e:
        collected_messages.append(f"[Stream error: {e}]")

    # Fetch artifacts if any
    for artifact_id in artifact_ids:
        artifact_content = fetch_artifact(base_url, artifact_id)
        if artifact_content:
            collected_messages.append(artifact_content)

    return "\n".join(collected_messages) if collected_messages else "[No response]"


def process_note(note: dict, base_url: str) -> str | None:
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

    # Format status messages differently
    if is_status:
        return f"[{agent_name}] {message}" if agent_name else f"[Status] {message}"

    return message


def fetch_artifact(base_url: str, artifact_id: str) -> str | None:
    """Fetch and format an artifact."""
    try:
        resp = httpx.post(
            f"{base_url}/get_artefact",
            json={"artefact_id": artifact_id},
            timeout=30.0,
        )
        if resp.status_code == 200:
            artifact = resp.json()
            parts = []

            # Add summary if present
            summary = artifact.get("summary", "").strip()
            if summary:
                parts.append(summary)

            # Add code if present
            code = artifact.get("code", "").strip()
            if code:
                parts.append(f"\n```\n{code}\n```")

            # Indicate if there's data (HTML table)
            data = artifact.get("data", "").strip()
            if data and "<table" in data.lower():
                parts.append("[Table data available]")

            # Indicate if there's an image
            image = artifact.get("image", "").strip()
            if image:
                parts.append("[Image generated]")

            return "\n".join(parts) if parts else None
    except Exception:
        pass
    return None
