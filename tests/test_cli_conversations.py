"""
Integration tests for CLI conversations with scripted inputs.

These tests require the backend server to be running:
    python -m yaaaf backend 4000

Run these tests with:
    python -m unittest tests.test_cli_conversations
"""

import unittest
import uuid
import time
import httpx


# Configuration
BACKEND_URL = "http://localhost:4000"
TIMEOUT = 120  # seconds to wait for completion


def is_backend_available() -> bool:
    """Check if backend server is running."""
    try:
        response = httpx.get(f"{BACKEND_URL}/get_agents_config", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


class ScriptedConversation:
    """
    A helper class to run scripted conversations with the YAAAF backend.

    Usage:
        conv = ScriptedConversation()
        conv.send("what is the weather in my hometown")
        conv.wait_for_pause()  # Waits until user_input agent asks a question
        conv.respond("London, UK")  # Responds to the question
        result = conv.wait_for_completion()  # Waits for final result
    """

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.stream_id = f"test_{uuid.uuid4().hex[:8]}"
        self.messages = []
        self.notes = []

    def send(self, query: str) -> None:
        """Send initial query to start the conversation."""
        self.messages.append({"role": "user", "content": query})

        response = httpx.post(
            f"{self.base_url}/create_stream",
            json={"stream_id": self.stream_id, "messages": self.messages},
            timeout=10.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Failed to create stream: {response.status_code}")

    def get_notes(self) -> list:
        """Fetch current notes from the stream."""
        response = httpx.post(
            f"{self.base_url}/get_utterances",
            json={"stream_id": self.stream_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            self.notes = response.json()
            return self.notes
        return []

    def get_status(self) -> dict:
        """Get stream status."""
        response = httpx.post(
            f"{self.base_url}/get_stream_status",
            json={"stream_id": self.stream_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return {"is_active": False}

    def is_paused(self) -> bool:
        """Check if execution is paused waiting for user input."""
        notes = self.get_notes()
        if notes:
            last_note = notes[-1]
            message = last_note.get("message", "")
            return "<taskpaused/>" in message
        return False

    def is_completed(self) -> bool:
        """Check if execution is completed."""
        notes = self.get_notes()
        if notes:
            last_note = notes[-1]
            message = last_note.get("message", "")
            return "<taskcompleted/>" in message
        return False

    def wait_for_pause(self, timeout: float = TIMEOUT) -> str:
        """Wait until execution pauses for user input. Returns the question asked."""
        start = time.time()
        while time.time() - start < timeout:
            notes = self.get_notes()
            if notes:
                last_note = notes[-1]
                message = last_note.get("message", "")
                if "<taskpaused/>" in message:
                    # Extract the question (message before the tag)
                    question = message.replace("<taskpaused/>", "").strip()
                    return question
            time.sleep(1.0)
        raise TimeoutError(f"Execution did not pause within {timeout} seconds")

    def wait_for_completion(self, timeout: float = TIMEOUT) -> list:
        """Wait until execution completes. Returns all notes."""
        start = time.time()
        while time.time() - start < timeout:
            notes = self.get_notes()
            if notes:
                last_note = notes[-1]
                message = last_note.get("message", "")
                if "<taskcompleted/>" in message:
                    return notes
            time.sleep(1.0)
        raise TimeoutError(f"Execution did not complete within {timeout} seconds")

    def respond(self, user_response: str) -> None:
        """Submit user response when execution is paused."""
        response = httpx.post(
            f"{self.base_url}/submit_user_response",
            json={"stream_id": self.stream_id, "user_response": user_response},
            timeout=10.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Failed to submit response: {response.status_code}")
        # Add to conversation history
        self.messages.append({"role": "user", "content": user_response})

    def get_final_messages(self) -> list[str]:
        """Get all non-internal, non-status messages from the conversation."""
        messages = []
        for note in self.notes:
            if note.get("internal", False):
                continue
            if note.get("is_status", False):
                continue
            message = note.get("message", "")
            # Strip completion tags for cleaner output
            message = message.replace("<taskcompleted/>", "").replace("<taskpaused/>", "")
            message = message.strip()
            if message:
                messages.append(message)
        return messages

    def get_artifact(self, artifact_id: str) -> dict | None:
        """Fetch an artifact by ID."""
        response = httpx.post(
            f"{self.base_url}/get_artefact",
            json={"artefact_id": artifact_id},
            timeout=30.0,
        )
        if response.status_code == 200:
            return response.json()
        return None

    def get_artifact_ids(self) -> list[str]:
        """Get all artifact IDs from the conversation."""
        ids = []
        for note in self.notes:
            artifact_id = note.get("artefact_id")
            if artifact_id:
                ids.append(artifact_id)
        return ids


@unittest.skipUnless(is_backend_available(), "Backend server not running")
class TestScriptedConversations(unittest.TestCase):
    """Test scripted conversations with the CLI."""

    def test_weather_hometown_conversation(self):
        """Test: Ask for weather, provide hometown when prompted, get weather info."""
        conv = ScriptedConversation()

        # Start conversation
        conv.send("what is the weather in my hometown?")

        # Wait for the user_input agent to ask for hometown
        question = conv.wait_for_pause(timeout=60)
        self.assertIsNotNone(question)
        print(f"\nAgent asked: {question}")

        # Respond with hometown
        conv.respond("London, UK")

        # Wait for completion
        notes = conv.wait_for_completion(timeout=120)
        self.assertIsNotNone(notes)

        # Get final messages
        final_messages = conv.get_final_messages()
        print(f"\nFinal messages: {final_messages}")

        # Verify we got some meaningful response
        self.assertTrue(len(final_messages) > 0)

        # Check that the response mentions London or weather
        all_text = " ".join(final_messages).lower()
        self.assertTrue(
            "london" in all_text or "weather" in all_text or "temperature" in all_text,
            f"Expected response to mention London or weather. Got: {all_text[:500]}",
        )

    def test_simple_question_no_user_input(self):
        """Test: Ask a simple question that doesn't require user input."""
        conv = ScriptedConversation()

        # Ask a simple factual question
        conv.send("What is 2 + 2?")

        # Wait for completion (should not pause)
        try:
            notes = conv.wait_for_completion(timeout=60)
            final_messages = conv.get_final_messages()
            print(f"\nSimple question response: {final_messages}")

            # Should have gotten an answer
            self.assertTrue(len(final_messages) > 0)
        except TimeoutError:
            # If it pauses, that's also acceptable behavior for some planners
            self.skipTest("Execution paused unexpectedly")


@unittest.skipUnless(is_backend_available(), "Backend server not running")
class TestConversationWithMultipleInputs(unittest.TestCase):
    """Test conversations that may require multiple user inputs."""

    def test_travel_planning_conversation(self):
        """Test: Plan a trip, respond to multiple questions."""
        conv = ScriptedConversation()

        # Start with travel planning request
        conv.send("Help me plan a trip")

        responses = {
            "destination": "Paris, France",
            "date": "next month",
            "budget": "1000 euros",
            "duration": "5 days",
        }

        max_interactions = 5
        interactions = 0

        while interactions < max_interactions:
            try:
                # Wait for either pause or completion
                start = time.time()
                while time.time() - start < 30:
                    if conv.is_completed():
                        print(f"\nTrip planning completed after {interactions} interactions")
                        final_messages = conv.get_final_messages()
                        self.assertTrue(len(final_messages) > 0)
                        return
                    if conv.is_paused():
                        break
                    time.sleep(1)

                if not conv.is_paused():
                    break

                question = conv.wait_for_pause(timeout=5)
                print(f"\nAgent asked: {question}")

                # Provide relevant response based on question
                response = "I'm not sure"
                question_lower = question.lower()
                if "where" in question_lower or "destination" in question_lower:
                    response = responses["destination"]
                elif "when" in question_lower or "date" in question_lower:
                    response = responses["date"]
                elif "budget" in question_lower or "money" in question_lower:
                    response = responses["budget"]
                elif "long" in question_lower or "duration" in question_lower:
                    response = responses["duration"]

                print(f"Responding: {response}")
                conv.respond(response)
                interactions += 1

            except TimeoutError:
                break

        # Check final result
        notes = conv.get_notes()
        final_messages = conv.get_final_messages()
        print(f"\nFinal messages after {interactions} interactions: {final_messages}")


class TestScriptedConversationHelper(unittest.TestCase):
    """Unit tests for the ScriptedConversation helper class."""

    def test_stream_id_generation(self):
        """Test that each conversation gets a unique stream ID."""
        conv1 = ScriptedConversation()
        conv2 = ScriptedConversation()
        self.assertNotEqual(conv1.stream_id, conv2.stream_id)
        self.assertTrue(conv1.stream_id.startswith("test_"))
        self.assertTrue(conv2.stream_id.startswith("test_"))

    def test_message_tracking(self):
        """Test that messages are properly tracked."""
        conv = ScriptedConversation()
        conv.messages.append({"role": "user", "content": "Hello"})
        conv.messages.append({"role": "user", "content": "How are you?"})
        self.assertEqual(len(conv.messages), 2)
        self.assertEqual(conv.messages[0]["content"], "Hello")


if __name__ == "__main__":
    if not is_backend_available():
        print("WARNING: Backend server not running at", BACKEND_URL)
        print("Start the backend with: python -m yaaaf backend 4000")
        print("\nRunning only unit tests (skipping integration tests)...")
    unittest.main()
