import asyncio
import unittest

from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages
from yaaaf.components.extractors.goal_extractor import GoalExtractor


class TestGoalExtractor(unittest.TestCase):
    def test_simple_exchange(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.7,
            max_tokens=100,
        )
        messages = Messages().add_user_utterance("I will need to know the time")
        goal_extractor = GoalExtractor(client=client)
        goal: str = asyncio.run(goal_extractor.extract(messages))
        expected: str = "time"
        self.assertIn(expected, goal)
