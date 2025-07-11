import asyncio
import unittest
from unittest.mock import Mock, patch

from yaaaf.components.agents.url_agent import URLAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages


class TestURLAgent(unittest.TestCase):
    def setUp(self):
        self.client = Mock(spec=OllamaClient)
        self.agent = URLAgent(self.client)

    def test_initialization(self):
        """Test that URLAgent initializes correctly."""
        self.assertIsNotNone(self.agent._client)
        self.assertEqual(self.agent.get_name(), "urlagent")
        self.assertIn("URL Analysis agent", self.agent.get_description())

    def test_get_description(self):
        """Test that the agent description is informative."""
        description = self.agent.get_description()
        self.assertIn("URL Analysis agent", description)
        self.assertIn("fetches content from URLs", description)
        # Test that XML tags are NOT in the description (tool-friendly)
        self.assertNotIn("<urlagent>", description)
        self.assertNotIn("</urlagent>", description)

    @patch("requests.get")
    def test_fetch_url_content_success(self, mock_get):
        """Test successful URL content fetching."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.text = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
            <h1>Main Title</h1>
            <p>This is test content.</p>
            <a href="https://example.com">Link</a>
        </body>
        </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        content = self.agent._fetch_url_content("https://example.com")

        # Should contain text content but not script/style
        self.assertIn("Main Title", content)
        self.assertIn("This is test content", content)
        self.assertNotIn("alert('test')", content)
        self.assertNotIn("color: red", content)

    @patch("requests.get")
    def test_fetch_url_content_error(self, mock_get):
        """Test URL content fetching with error."""
        mock_get.side_effect = Exception("Connection failed")

        content = self.agent._fetch_url_content("https://invalid-url.com")

        self.assertIn("Error fetching URL", content)
        self.assertIn("Connection failed", content)

    def test_extract_urls_from_content(self):
        """Test URL extraction from HTML content."""
        html_content = """
        <a href="https://example.com/page1">Page 1</a>
        <a href="/relative/page">Relative Page</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="https://another.com">Another Site</a>
        """

        urls = self.agent._extract_urls_from_content(
            html_content, "https://example.com"
        )

        # Should contain absolute URLs
        self.assertIn("https://example.com/page1", urls)
        self.assertIn(
            "https://example.com/relative/page", urls
        )  # Converted from relative
        self.assertIn("https://another.com", urls)
        # Should not contain mailto links
        self.assertNotIn("mailto:test@example.com", urls)

    @patch("yaaaf.components.agents.url_agent.URLAgent._fetch_url_content")
    def test_query_with_text_response(self, mock_fetch):
        """Test agent query that returns text analysis."""
        # Mock URL content
        mock_fetch.return_value = "This is a test page about machine learning and AI."

        # Mock client responses - need to be async
        async def mock_predict(*args, **kwargs):
            if hasattr(mock_predict, "call_count"):
                mock_predict.call_count += 1
            else:
                mock_predict.call_count = 1

            if mock_predict.call_count == 1:
                return """I need to analyze the URL for machine learning content.
                ```url
                https://example.com/ml-article
                Find information about machine learning
                ```"""
            else:
                return "The page contains information about machine learning and AI technologies."

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance(
            "Analyze https://example.com/ml-article for machine learning content"
        )

        result = asyncio.run(self.agent.query(messages))

        self.assertIn("machine learning", result.lower())
        self.assertNotIn("<taskcompleted/>", result)

    @patch("yaaaf.components.agents.url_agent.URLAgent._fetch_url_content")
    @patch("yaaaf.components.agents.url_agent.URLAgent._extract_urls_from_content")
    def test_query_with_url_table_response(self, mock_extract_urls, mock_fetch):
        """Test agent query that returns URL table."""
        # Mock URL content and extracted URLs
        mock_fetch.return_value = "Page with various links to resources"
        mock_extract_urls.return_value = [
            "https://example.com/resource1",
            "https://example.com/resource2",
            "https://another.com/tool",
        ]

        # Mock client response - async
        async def mock_predict(*args, **kwargs):
            return """I need to find URLs about AI tools.
            ```url
            https://example.com/ai-tools
            find links to AI tools and resources
            ```"""

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance(
            "Find AI tool URLs from https://example.com/ai-tools"
        )

        result = asyncio.run(self.agent.query(messages))

        # Should return artifact reference
        self.assertIn("artifact", result.lower())
        self.assertIn("url-analysis", result)

    @patch("yaaaf.components.agents.url_agent.URLAgent._fetch_url_content")
    def test_query_with_malformed_input(self, mock_fetch):
        """Test agent query with malformed input."""
        # Mock URL content
        mock_fetch.return_value = "This is test content from the URL."

        # Mock client response with malformed URL block - async
        call_count = 0

        async def mock_predict(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "I want to analyze a URL but forgot the format"
            elif call_count == 2:
                return """Let me try again:
                ```url
                https://example.com
                analyze this page
                ```"""
            else:
                return "<taskcompleted/> Analysis complete"

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance("Analyze some URL")

        result = asyncio.run(self.agent.query(messages))

        # Should handle the malformed input gracefully
        self.assertIsInstance(result, str)

    def test_opening_and_closing_tags(self):
        """Test that agent has correct HTML-like tags."""
        self.assertEqual(self.agent.get_opening_tag(), "<urlagent>")
        self.assertEqual(self.agent.get_closing_tag(), "</urlagent>")

    @patch("requests.get")
    def test_content_length_limiting(self, mock_get):
        """Test that content is limited to prevent excessive data."""
        # Create very long content
        mock_response = Mock()
        mock_response.text = f"<html><body>{'A' * 15000}</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        content = self.agent._fetch_url_content("https://example.com")

        # Should be limited to 10k characters
        self.assertLessEqual(len(content), 10000)


if __name__ == "__main__":
    unittest.main()
