import unittest
from yaaaf.components.safety_filter import SafetyFilter
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.server.config import SafetyFilterSettings


class TestSafetyFilter(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.safe_settings = SafetyFilterSettings(enabled=False)
        self.unsafe_settings = SafetyFilterSettings(
            enabled=True,
            blocked_keywords=["harmful", "dangerous", "illegal"],
            blocked_patterns=[r"how to.*hack", r"create.*virus"],
            custom_message="I cannot answer that",
        )

    def test_disabled_filter_allows_all(self):
        """Test that disabled filter allows all messages."""
        filter = SafetyFilter(self.safe_settings)

        messages = Messages(
            utterances=[Utterance(role="user", content="How to hack a system?")]
        )

        self.assertTrue(filter.is_safe(messages))

    def test_enabled_filter_blocks_keywords(self):
        """Test that enabled filter blocks messages with blocked keywords."""
        filter = SafetyFilter(self.unsafe_settings)

        # Test blocked keyword
        messages = Messages(
            utterances=[Utterance(role="user", content="This is a harmful request")]
        )

        self.assertFalse(filter.is_safe(messages))

    def test_enabled_filter_blocks_patterns(self):
        """Test that enabled filter blocks messages matching blocked patterns."""
        filter = SafetyFilter(self.unsafe_settings)

        # Test blocked pattern
        messages = Messages(
            utterances=[Utterance(role="user", content="How to hack into a database?")]
        )

        self.assertFalse(filter.is_safe(messages))

    def test_enabled_filter_allows_safe_content(self):
        """Test that enabled filter allows safe messages."""
        filter = SafetyFilter(self.unsafe_settings)

        # Test safe content
        messages = Messages(
            utterances=[Utterance(role="user", content="What is the weather today?")]
        )

        self.assertTrue(filter.is_safe(messages))

    def test_case_insensitive_matching(self):
        """Test that keyword matching is case insensitive."""
        filter = SafetyFilter(self.unsafe_settings)

        # Test uppercase keyword
        messages = Messages(
            utterances=[Utterance(role="user", content="This is HARMFUL content")]
        )

        self.assertFalse(filter.is_safe(messages))

    def test_multiple_messages(self):
        """Test filtering across multiple messages."""
        filter = SafetyFilter(self.unsafe_settings)

        # Test with multiple messages, one containing blocked content
        messages = Messages(
            utterances=[
                Utterance(role="user", content="Hello there"),
                Utterance(role="assistant", content="Hi! How can I help?"),
                Utterance(role="user", content="Tell me something illegal"),
            ]
        )

        self.assertFalse(filter.is_safe(messages))

    def test_get_safety_message(self):
        """Test that the correct safety message is returned."""
        filter = SafetyFilter(self.unsafe_settings)

        self.assertEqual(filter.get_safety_message(), "I cannot answer that")

    def test_invalid_regex_pattern(self):
        """Test handling of invalid regex patterns."""
        settings = SafetyFilterSettings(
            enabled=True,
            blocked_patterns=["[invalid regex"],
            custom_message="I cannot answer that",
        )

        filter = SafetyFilter(settings)

        # Should not crash and should allow content when regex is invalid
        messages = Messages(utterances=[Utterance(role="user", content="Some content")])

        self.assertTrue(filter.is_safe(messages))


if __name__ == "__main__":
    unittest.main()
