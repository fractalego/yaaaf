import re
import logging

from yaaaf.components.data_types import Messages
from yaaaf.server.config import SafetyFilterSettings

_logger = logging.getLogger(__name__)


class SafetyFilter:
    """Safety filter to check user queries against configured safety conditions."""

    def __init__(self, settings: SafetyFilterSettings):
        self.settings = settings
        self.enabled = settings.enabled
        self.blocked_keywords = [
            keyword.lower() for keyword in settings.blocked_keywords
        ]
        self.blocked_patterns = settings.blocked_patterns
        self.custom_message = settings.custom_message

        _logger.info(f"Safety filter initialized - Enabled: {self.enabled}")
        if self.enabled:
            _logger.info(f"Blocked keywords: {len(self.blocked_keywords)}")
            _logger.info(f"Blocked patterns: {len(self.blocked_patterns)}")

    def is_safe(self, messages: Messages) -> bool:
        """
        Check if the messages are safe according to the configured filters.

        Args:
            messages: The Messages object containing user queries

        Returns:
            bool: True if safe, False if blocked
        """
        if not self.enabled:
            return True

        # Extract text content from all messages
        text_content = self._extract_text_from_messages(messages)

        # Check against blocked keywords
        if self._contains_blocked_keywords(text_content):
            _logger.warning(
                f"Query blocked due to keyword match: {text_content[:100]}..."
            )
            return False

        # Check against blocked patterns
        if self._matches_blocked_patterns(text_content):
            _logger.warning(
                f"Query blocked due to pattern match: {text_content[:100]}..."
            )
            return False

        return True

    def get_safety_message(self) -> str:
        """Get the custom safety message to return when content is blocked."""
        return self.custom_message

    def _extract_text_from_messages(self, messages: Messages) -> str:
        """Extract all text content from messages for analysis."""
        text_parts = []
        for utterance in messages.utterances:
            if utterance.content:
                text_parts.append(utterance.content)
        return " ".join(text_parts).lower()

    def _contains_blocked_keywords(self, text: str) -> bool:
        """Check if text contains any blocked keywords."""
        for keyword in self.blocked_keywords:
            if keyword in text:
                return True
        return False

    def _matches_blocked_patterns(self, text: str) -> bool:
        """Check if text matches any blocked regex patterns."""
        for pattern in self.blocked_patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            except re.error as e:
                _logger.error(f"Invalid regex pattern '{pattern}': {e}")
        return False
