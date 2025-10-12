import unittest

from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types.tools import ClientResponse
from yaaaf.components.agents.tokens_utils import extract_thinking_content
from yaaaf.components.agents.base_agent import BaseAgent


class MockClient(OllamaClient):
    """Mock client for testing thinking artifacts."""

    def __init__(self):
        # Initialize without calling parent constructor to avoid file loading
        self.model = "test-model"

    async def predict(self, messages, stop_sequences=None, tools=None):
        # Return a response with thinking content
        return ClientResponse(
            message="This is the answer after thinking",
            tool_calls=None,
            thinking_content="I need to analyze this question carefully and consider multiple aspects.",
        )


class TestThinkingArtifacts(unittest.TestCase):
    def test_extract_thinking_content(self):
        """Test that thinking content is properly extracted from responses."""
        # Test with thinking content
        response_with_thinking = "<think>This is my thinking</think>This is the answer"
        thinking, answer = extract_thinking_content(response_with_thinking)

        self.assertEqual(thinking, "This is my thinking")
        self.assertEqual(answer, "This is the answer")

        # Test without thinking content
        response_without_thinking = "This is just an answer"
        thinking, answer = extract_thinking_content(response_without_thinking)

        self.assertEqual(thinking, "")
        self.assertEqual(answer, "This is just an answer")

    def test_client_response_with_thinking(self):
        """Test that ClientResponse properly handles thinking content."""
        response = ClientResponse(
            message="Regular answer",
            tool_calls=None,
            thinking_content="Thinking content",
        )

        self.assertEqual(response.message, "Regular answer")
        self.assertEqual(response.thinking_content, "Thinking content")
        self.assertIsNone(response.tool_calls)

    def test_base_agent_thinking_artifact_creation(self):
        """Test that BaseAgent can create thinking artifacts."""
        from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact

        # Create a test agent
        agent = BaseAgent()
        agent._storage = ArtefactStorage()

        # Create a mock client response
        response = ClientResponse(
            message="Test answer",
            tool_calls=None,
            thinking_content="This is my thinking process",
        )

        notes = []
        artifact_ref = agent._create_thinking_artifact(response, notes)

        # Verify artifact was created
        self.assertIsNotNone(artifact_ref)
        self.assertIn("artefact type='thinking'", artifact_ref)

        # Verify note was added
        self.assertEqual(len(notes), 1)
        self.assertIn("Created thinking artifact", notes[0].message)

        # Extract artifact ID and verify it's stored
        import re

        match = re.search(r"<artefact type='thinking'>([^<]+)</artefact>", artifact_ref)
        self.assertIsNotNone(match)

        artifact_id = match.group(1)
        stored_artifact = agent._storage.retrieve_from_id(artifact_id)

        self.assertEqual(stored_artifact.type, Artefact.Types.THINKING)
        self.assertEqual(stored_artifact.code, "This is my thinking process")
        self.assertIn("Thinking process from", stored_artifact.description)


if __name__ == "__main__":
    unittest.main()
