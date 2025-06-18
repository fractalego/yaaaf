import json
import os
import tempfile
import unittest
from unittest.mock import patch

from yaaaf.config_generator import ConfigGenerator


class TestConfigGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = ConfigGenerator()

    def test_initial_config_structure(self):
        """Test that the initial config has the expected structure."""
        expected_keys = {"client", "agents", "sources"}
        self.assertEqual(set(self.generator.config.keys()), expected_keys)

        # Check client defaults
        client = self.generator.config["client"]
        self.assertIn("model", client)
        self.assertIn("temperature", client)
        self.assertIn("max_tokens", client)

        # Check initial state
        self.assertEqual(self.generator.config["agents"], [])
        self.assertEqual(self.generator.config["sources"], [])

    def test_available_agents(self):
        """Test that all expected agents are available."""
        expected_agents = {
            "reflection",
            "visualization",
            "sql",
            "rag",
            "reviewer",
            "websearch",
            "url_reviewer",
        }
        self.assertEqual(set(self.generator.available_agents.keys()), expected_agents)

    @patch("builtins.input")
    def test_get_input_with_default(self, mock_input):
        """Test getting input with default value."""
        mock_input.return_value = ""  # User presses enter
        result = self.generator.get_input("Test prompt", "default_value")
        self.assertEqual(result, "default_value")

    @patch("builtins.input")
    def test_get_yes_no(self, mock_input):
        """Test yes/no input handling."""
        # Test yes responses
        for yes_response in ["y", "yes", "Y", "YES"]:
            mock_input.return_value = yes_response
            self.assertTrue(self.generator.get_yes_no("Test?"))

        # Test no responses
        for no_response in ["n", "no", "N", "NO"]:
            mock_input.return_value = no_response
            self.assertFalse(self.generator.get_yes_no("Test?"))

    def test_config_save_and_load(self):
        """Test saving and loading configuration."""
        # Create a sample configuration
        test_config = {
            "client": {"model": "test_model", "temperature": 0.5, "max_tokens": 512},
            "agents": ["reflection", "rag"],
            "sources": [
                {
                    "name": "test_source",
                    "type": "text",
                    "path": "/test/path",
                    "description": "Test source",
                }
            ],
        }

        self.generator.config = test_config

        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            json.dump(self.generator.config, tmp_file, indent=2)
            temp_path = tmp_file.name

        try:
            # Load and verify
            with open(temp_path, "r") as f:
                loaded_config = json.load(f)

            self.assertEqual(loaded_config, test_config)
        finally:
            os.unlink(temp_path)

    @patch("builtins.input")
    def test_configure_client_basic(self, mock_input):
        """Test basic client configuration."""
        # Mock user inputs: model name, temp 0.8, tokens 2048
        mock_input.side_effect = ["llama3.1:8b", "0.8", "2048"]

        self.generator.configure_client()

        self.assertEqual(self.generator.config["client"]["model"], "llama3.1:8b")
        self.assertEqual(self.generator.config["client"]["temperature"], 0.8)
        self.assertEqual(self.generator.config["client"]["max_tokens"], 2048)

    @patch("builtins.input")
    def test_configure_agents_selection(self, mock_input):
        """Test agent selection."""
        # Mock selecting reflection and rag agents
        responses = []
        for agent in self.generator.available_agents.keys():
            if agent in ["reflection", "rag"]:
                responses.append("y")  # Enable these agents
            else:
                responses.append("n")  # Disable others

        mock_input.side_effect = responses

        self.generator.configure_agents()

        self.assertIn("reflection", self.generator.config["agents"])
        self.assertIn("rag", self.generator.config["agents"])
        self.assertEqual(len(self.generator.config["agents"]), 2)

    def test_agent_descriptions_exist(self):
        """Test that all agents have descriptions."""
        for agent_name in self.generator.available_agents:
            description = self.generator.available_agents[agent_name]
            self.assertIsInstance(description, str)
            self.assertGreater(len(description), 10)  # Reasonable description length


    @patch("builtins.input")
    @patch("os.path.exists")
    def test_add_text_source_file(self, mock_exists, mock_input):
        """Test adding a text source file."""
        # Setup mocks
        mock_exists.return_value = True
        test_file_path = "/test/document.txt"

        # Mock user inputs: yes to add source, path, name, description
        mock_input.side_effect = [
            "y",  # Add text source
            test_file_path,  # File path
            "test_doc",  # Source name
            "Test document",  # Description
            "n",  # Don't add more sources
        ]

        # Add rag to agents first
        self.generator.config["agents"] = ["rag"]

        with patch("os.path.isfile", return_value=True):
            self.generator.add_text_sources()

        # Check that source was added
        self.assertEqual(len(self.generator.config["sources"]), 1)
        source = self.generator.config["sources"][0]
        self.assertEqual(source["name"], "test_doc")
        self.assertEqual(source["type"], "text")
        self.assertEqual(source["path"], test_file_path)
        self.assertEqual(source["description"], "Test document")


if __name__ == "__main__":
    unittest.main()
