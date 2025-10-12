import unittest
from unittest.mock import Mock, AsyncMock
import pandas as pd

from yaaaf.components.extractors.status_extractor import StatusExtractor
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.client import OllamaClient


class TestStatusExtractor(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock(spec=OllamaClient)
        self.extractor = StatusExtractor(self.mock_client)
        self.storage = ArtefactStorage()

        # Create a sample todo list DataFrame
        self.sample_df = pd.DataFrame(
            {
                "ID": ["1", "2", "3"],
                "Task": ["Parse query", "Execute SQL", "Generate visualization"],
                "Status": ["completed", "pending", "pending"],
                "Agent/Tool": ["TodoAgent", "SQLAgent", "VisualizationAgent"],
            }
        )

        # Store as artifact
        self.todo_artifact = Artefact(
            type=Artefact.Types.TODO_LIST,
            data=self.sample_df,
            description="Test todo list",
            id="test_todo_123",
        )
        self.storage.store_artefact("test_todo_123", self.todo_artifact)

    def test_get_current_step_info(self):
        """Test extracting current step information."""
        step_info = self.extractor.get_current_step_info("test_todo_123")

        self.assertIsInstance(step_info, dict)
        self.assertEqual(step_info["total_steps"], 3)
        self.assertEqual(
            step_info["current_step_index"], 2
        )  # First pending task (1-indexed)
        self.assertEqual(step_info["current_step_description"], "Execute SQL")
        self.assertIn("markdown_todo_list", step_info)

    def test_generate_markdown_todo_list(self):
        """Test markdown todo list generation."""
        markdown = self.extractor._generate_markdown_todo_list(
            self.sample_df, 1
        )  # Index 1 is current

        self.assertIn("[x] Parse query", markdown)
        self.assertIn("[🔄] **Execute SQL** ←─ CURRENT STEP", markdown)
        self.assertIn("[ ] Generate visualization", markdown)

    def test_fallback_status_evaluation(self):
        """Test fallback status evaluation."""
        self.assertEqual(
            self.extractor._fallback_status_evaluation(
                "Task completed <taskcompleted/>", "pending"
            ),
            "completed",
        )
        self.assertEqual(
            self.extractor._fallback_status_evaluation(
                "The task is complete.", "pending"
            ),
            "completed",
        )
        self.assertEqual(
            self.extractor._fallback_status_evaluation("Working on it...", "pending"),
            "in_progress",
        )
        self.assertEqual(
            self.extractor._fallback_status_evaluation("", "pending"), "pending"
        )

    def test_has_meaningful_content(self):
        """Test meaningful content detection."""
        self.assertTrue(
            self.extractor._has_meaningful_content(
                "This is a substantial response with content."
            )
        )
        self.assertFalse(self.extractor._has_meaningful_content("<tag></tag>"))
        self.assertFalse(self.extractor._has_meaningful_content("   "))

    async def test_llm_evaluate_step_completion(self):
        """Test LLM-based step evaluation."""
        # Mock the client response
        mock_response = Mock()
        mock_response.message = "completed"
        self.extractor._client.predict = AsyncMock(return_value=mock_response)

        result = await self.extractor._llm_evaluate_step_completion(
            "Execute SQL query",
            "Query executed successfully: SELECT * FROM users returned 10 rows",
            "SQLAgent",
        )

        self.assertEqual(result, "completed")
        self.extractor._client.predict.assert_called_once()


if __name__ == "__main__":
    unittest.main()
