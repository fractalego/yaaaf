import unittest
from unittest.mock import Mock, patch
from yaaaf.components.agents.brave_search_agent import BraveSearchAgent
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.server.config import Settings, ClientSettings, APISettings


class TestBraveSearchAgent(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()

        # Mock config with API key
        with patch(
            "yaaaf.components.agents.brave_search_agent.get_config"
        ) as mock_get_config:
            mock_config = Settings(
                client=ClientSettings(),
                api_keys=APISettings(brave_search_api_key="test-api-key"),
            )
            mock_get_config.return_value = mock_config
            self.agent = BraveSearchAgent(self.mock_client)

    def test_initialization_with_api_key(self):
        """Test that agent initializes correctly with API key."""
        with patch(
            "yaaaf.components.agents.brave_search_agent.get_config"
        ) as mock_get_config:
            mock_config = Settings(
                client=ClientSettings(),
                api_keys=APISettings(brave_search_api_key="test-key"),
            )
            mock_get_config.return_value = mock_config
            agent = BraveSearchAgent(self.mock_client)
            self.assertEqual(agent._api_key, "test-key")

    def test_initialization_without_api_key(self):
        """Test that agent raises error when API key is missing."""
        with patch(
            "yaaaf.components.agents.brave_search_agent.get_config"
        ) as mock_get_config:
            mock_config = Settings(
                client=ClientSettings(), api_keys=APISettings(brave_search_api_key=None)
            )
            mock_get_config.return_value = mock_config

            with self.assertRaises(ValueError) as context:
                BraveSearchAgent(self.mock_client)

            self.assertIn("Brave Search API key is required", str(context.exception))

    def test_get_description(self):
        """Test that get_description returns correct description."""
        description = self.agent.get_description()
        self.assertIn("Brave Web Search agent", description)
        self.assertIn("Brave Search engine", description)
        self.assertIn(self.agent.get_opening_tag(), description)
        self.assertIn(self.agent.get_closing_tag(), description)

    def test_get_name(self):
        """Test that get_name returns correct agent name."""
        self.assertEqual(self.agent.get_name(), "bravesearchagent")

    @patch("yaaaf.components.agents.brave_search_agent.requests.get")
    def test_search_brave_success(self, mock_get):
        """Test successful Brave search API call."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Test Title 1",
                        "description": "Test description 1",
                        "url": "https://example1.com",
                    },
                    {
                        "title": "Test Title 2",
                        "description": "Test description 2",
                        "url": "https://example2.com",
                    },
                ]
            }
        }
        mock_get.return_value = mock_response

        results = self.agent._search_brave("test query")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Test Title 1")
        self.assertEqual(results[0]["body"], "Test description 1")
        self.assertEqual(results[0]["href"], "https://example1.com")

        # Verify API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("X-Subscription-Token", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["X-Subscription-Token"], "test-api-key")
        self.assertEqual(kwargs["params"]["q"], "test query")

    @patch("yaaaf.components.agents.brave_search_agent.requests.get")
    def test_search_brave_api_error(self, mock_get):
        """Test Brave search API error handling."""
        # Mock API error
        mock_get.side_effect = Exception("API Error")

        results = self.agent._search_brave("test query")

        self.assertEqual(results, [])

    @patch("yaaaf.components.agents.brave_search_agent.requests.get")
    def test_search_brave_empty_response(self, mock_get):
        """Test Brave search with empty response."""
        # Mock empty response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"web": {"results": []}}
        mock_get.return_value = mock_response

        results = self.agent._search_brave("test query")

        self.assertEqual(results, [])

    @patch("yaaaf.components.agents.brave_search_agent.requests.get")
    async def test_query_method(self, mock_get):
        """Test the main query method."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Test Result",
                        "description": "Test description",
                        "url": "https://example.com",
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        # Mock client response
        self.mock_client.predict.return_value = (
            "```text\ntest search query\n```\n<taskcompleted/>"
        )

        messages = Messages(
            utterances=[
                Utterance(role="user", content="Search for information about Python")
            ]
        )

        result = await self.agent.query(messages)

        # Should return artifact reference
        self.assertIn("artifact", result)
        self.assertIn("brave-search-result", result)


if __name__ == "__main__":
    unittest.main()
