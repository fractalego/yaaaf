"""Unit tests for OutputRefiner."""

import unittest
import pandas as pd

from yaaaf.components.output_refiner import OutputRefiner, extract_artifact_id
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage


class TestOutputRefiner(unittest.TestCase):
    """Test cases for OutputRefiner class."""

    def setUp(self):
        """Set up test fixtures."""
        self.storage = ArtefactStorage()
        self.refiner = OutputRefiner(self.storage)

    def test_extract_artifact_id(self):
        """Test extracting artifact ID from completion message."""
        message = "Operation completed. Result: <artefact type='table'>abc123</artefact> <taskcompleted/>"
        artifact_id = extract_artifact_id(message)
        self.assertEqual(artifact_id, "abc123")

    def test_extract_artifact_id_with_image(self):
        """Test extracting artifact ID from image completion message."""
        message = "Operation completed. Result: <artefact type='image'>xyz789</artefact> <taskcompleted/>"
        artifact_id = extract_artifact_id(message)
        self.assertEqual(artifact_id, "xyz789")

    def test_extract_artifact_id_no_match(self):
        """Test extracting artifact ID when no artifact present."""
        message = "Operation completed. No artifact. <taskcompleted/>"
        artifact_id = extract_artifact_id(message)
        self.assertIsNone(artifact_id)

    def test_format_table_small(self):
        """Test formatting a small table."""
        # Create a test DataFrame
        df = pd.DataFrame({
            "Name": ["Alice", "Bob", "Charlie"],
            "Age": [25, 30, 35],
            "City": ["New York", "London", "Paris"]
        })

        # Store as artifact
        artifact = Artefact(
            type=Artefact.Types.TABLE,
            data=df,
            id="test123"
        )
        self.storage.store_artefact("test123", artifact)

        # Format the artifact
        formatted = self.refiner.format_artifact("test123")

        # Verify it's markdown
        self.assertIsNotNone(formatted)
        self.assertIn("Name", formatted)
        self.assertIn("Alice", formatted)
        self.assertIn("|", formatted)  # Markdown table delimiter

    def test_format_table_large(self):
        """Test formatting a large table (>20 rows)."""
        # Create a test DataFrame with 50 rows
        df = pd.DataFrame({
            "Index": range(50),
            "Value": [f"Value_{i}" for i in range(50)]
        })

        # Store as artifact
        artifact = Artefact(
            type=Artefact.Types.TABLE,
            data=df,
            id="large_table"
        )
        self.storage.store_artefact("large_table", artifact)

        # Format the artifact
        formatted = self.refiner.format_artifact("large_table")

        # Verify it's truncated
        self.assertIsNotNone(formatted)
        self.assertIn("Showing 20 of 50 rows", formatted)
        self.assertIn("Value_19", formatted)  # Row 19 should be included
        self.assertNotIn("Value_20", formatted)  # Row 20 should not be included

    def test_format_image(self):
        """Test formatting an image artifact."""
        # Create a test image artifact with base64 data
        base64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        artifact = Artefact(
            type=Artefact.Types.IMAGE,
            image=base64_image,
            id="img123"
        )
        self.storage.store_artefact("img123", artifact)

        # Format the artifact
        formatted = self.refiner.format_artifact("img123")

        # Verify it's markdown image
        self.assertIsNotNone(formatted)
        self.assertTrue(formatted.startswith("![Visualization](data:image/png;base64,"))
        self.assertIn(base64_image, formatted)

    def test_format_text_returns_none(self):
        """Test that text artifacts are not refined."""
        artifact = Artefact(
            type=Artefact.Types.TEXT,
            code="Some text content",
            id="text123"
        )
        self.storage.store_artefact("text123", artifact)

        # Format the artifact
        formatted = self.refiner.format_artifact("text123")

        # Text artifacts should not be refined
        self.assertIsNone(formatted)

    def test_format_empty_table(self):
        """Test formatting an empty table."""
        df = pd.DataFrame()

        artifact = Artefact(
            type=Artefact.Types.TABLE,
            data=df,
            id="empty"
        )
        self.storage.store_artefact("empty", artifact)

        # Format the artifact
        formatted = self.refiner.format_artifact("empty")

        # Should return a message about empty table
        self.assertIsNotNone(formatted)
        self.assertIn("Empty table", formatted)


if __name__ == "__main__":
    unittest.main()
