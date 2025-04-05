import unittest
from typing import List

from src.components.client import OllamaClient
from src.components.data_types import Messages
from src.components.agents.visualization_agent import VisualizationAgent
from src.components.extractors.goal_extractor import GoalExtractor


class TestGoalExtractor(unittest.TestCase):
    def test_simple_exchange(self):
        client = OllamaClient(
            model="gemma3:4b",
            temperature=0.7,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "I will need to know the time"
        )
        goal_extractor = GoalExtractor(client=client)
        goal: str = goal_extractor.extract(messages)
        expected: str = "time"
        self.assertIn(expected, goal)