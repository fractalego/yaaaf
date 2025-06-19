import unittest
import tempfile
import json
from pathlib import Path
from yaaaf.components.client import OllamaClient


class TestOllamaClientTrainingCutoff(unittest.TestCase):
    """Test the training cutoff date functionality of OllamaClient."""

    def setUp(self):
        """Set up test environment with sample cutoffs data."""
        self.sample_cutoffs_data = {
            "model_training_cutoffs": {
                "qwen2.5:32b": "October 2023",
                "qwen2.5:7b": "October 2023",
                "qwen2.5-coder:32b": "June 2024",
                "qwen3:8b": "November 2024",
                "llama3.1:8b": "April 2024",
                "llama3.3:70b": "December 2024",
                "gemma3:12b": "November 2024",
            },
            "pattern_matching": {
                "qwen2.5": {"default": "October 2023", "coder": "June 2024"},
                "qwen3": "November 2024",
                "llama3.1": "April 2024",
                "llama3.3": "December 2024",
                "gemma3": "November 2024",
            },
        }

    def _create_temp_cutoffs_file(self, data=None):
        """Create a temporary cutoffs file for testing."""
        if data is None:
            data = self.sample_cutoffs_data

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, temp_file)
        temp_file.close()
        return temp_file.name

    def test_default_cutoffs_file_loading(self):
        """Test that the default cutoffs file is loaded correctly."""
        # This uses the actual default JSON file
        client = OllamaClient(model="qwen2.5:32b")
        cutoff_date = client.get_training_cutoff_date()
        self.assertEqual(cutoff_date, "October 2023")
        self.assertIsNotNone(client._cutoffs_data)

    def test_custom_cutoffs_file_loading(self):
        """Test loading from a custom cutoffs file."""
        cutoffs_file = self._create_temp_cutoffs_file()
        try:
            client = OllamaClient(model="qwen2.5:32b", cutoffs_file=cutoffs_file)
            cutoff_date = client.get_training_cutoff_date()
            self.assertEqual(cutoff_date, "October 2023")
        finally:
            Path(cutoffs_file).unlink()

    def test_missing_cutoffs_file(self):
        """Test behavior when cutoffs file is missing."""
        client = OllamaClient(
            model="qwen2.5:32b", cutoffs_file="/nonexistent/file.json"
        )
        cutoff_date = client.get_training_cutoff_date()
        self.assertIsNone(cutoff_date)

    def test_invalid_json_cutoffs_file(self):
        """Test behavior when cutoffs file contains invalid JSON."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        temp_file.write("invalid json content")
        temp_file.close()

        try:
            client = OllamaClient(model="qwen2.5:32b", cutoffs_file=temp_file.name)
            cutoff_date = client.get_training_cutoff_date()
            self.assertIsNone(cutoff_date)
        finally:
            Path(temp_file.name).unlink()

    def test_known_model_cutoff_dates(self):
        """Test that known models return correct cutoff dates."""
        cutoffs_file = self._create_temp_cutoffs_file()
        try:
            test_cases = [
                ("qwen2.5:32b", "October 2023"),
                ("qwen2.5:7b", "October 2023"),
                ("qwen2.5-coder:32b", "June 2024"),
                ("qwen3:8b", "November 2024"),
                ("llama3.1:8b", "April 2024"),
                ("llama3.3:70b", "December 2024"),
                ("gemma3:12b", "November 2024"),
            ]

            for model_name, expected_date in test_cases:
                with self.subTest(model=model_name):
                    client = OllamaClient(model=model_name, cutoffs_file=cutoffs_file)
                    actual_date = client.get_training_cutoff_date()
                    self.assertEqual(actual_date, expected_date)
        finally:
            Path(cutoffs_file).unlink()

    def test_pattern_matching_case_insensitive(self):
        """Test that pattern matching works case-insensitively."""
        cutoffs_file = self._create_temp_cutoffs_file()
        try:
            test_cases = [
                ("Qwen2.5:32B", "October 2023"),
                ("QWEN2.5:7B", "October 2023"),
                ("qwen2.5-CODER:latest", "June 2024"),
                ("Llama3.1:70B", "April 2024"),
                ("GEMMA3:12B", "November 2024"),
            ]

            for model_name, expected_date in test_cases:
                with self.subTest(model=model_name):
                    client = OllamaClient(model=model_name, cutoffs_file=cutoffs_file)
                    actual_date = client.get_training_cutoff_date()
                    self.assertEqual(actual_date, expected_date)
        finally:
            Path(cutoffs_file).unlink()

    def test_unknown_model_returns_none(self):
        """Test that unknown models return None."""
        cutoffs_file = self._create_temp_cutoffs_file()
        try:
            unknown_models = [
                "unknown-model:latest",
                "custom:1.0",
                "some-random-model",
            ]

            for model_name in unknown_models:
                with self.subTest(model=model_name):
                    client = OllamaClient(model=model_name, cutoffs_file=cutoffs_file)
                    actual_date = client.get_training_cutoff_date()
                    self.assertIsNone(actual_date)
        finally:
            Path(cutoffs_file).unlink()

    def test_caching_behavior(self):
        """Test that the cutoff date is cached after first call."""
        cutoffs_file = self._create_temp_cutoffs_file()
        try:
            client = OllamaClient(model="qwen2.5:32b", cutoffs_file=cutoffs_file)

            # First call should compute and cache
            first_result = client.get_training_cutoff_date()
            self.assertEqual(first_result, "October 2023")

            # Second call should use cached value
            second_result = client.get_training_cutoff_date()
            self.assertEqual(second_result, "October 2023")
            self.assertEqual(first_result, second_result)

            # Check that internal cache is set
            self.assertEqual(client._training_cutoff_date, "October 2023")
        finally:
            Path(cutoffs_file).unlink()

    def test_model_family_patterns(self):
        """Test pattern matching for model families."""
        cutoffs_file = self._create_temp_cutoffs_file()
        try:
            test_cases = [
                ("qwen2.5:any-size", "October 2023"),
                ("qwen2.5-coder:any-size", "June 2024"),
                ("qwen3:any-size", "November 2024"),
                ("llama3.1:any-size", "April 2024"),
                ("llama3.3:any-size", "December 2024"),
                ("gemma3:any-size", "November 2024"),
            ]

            for model_name, expected_date in test_cases:
                with self.subTest(model=model_name):
                    client = OllamaClient(model=model_name, cutoffs_file=cutoffs_file)
                    actual_date = client.get_training_cutoff_date()
                    self.assertEqual(actual_date, expected_date)
        finally:
            Path(cutoffs_file).unlink()


if __name__ == "__main__":
    unittest.main()
