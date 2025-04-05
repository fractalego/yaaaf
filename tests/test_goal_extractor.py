import unittest
from typing import List

from yaaf.components.client import OllamaClient
from yaaf.components.data_types import Messages
from yaaf.components.agents.visualization_agent import VisualizationAgent
from yaaf.components.extractors.goal_extractor import GoalExtractor


class TestGoalExtractor(unittest.TestCase):
    def test_simple_exchange(self):
        client = OllamaClient(
            model="gemma3:4b",
            temperature=0.7,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance("I will need to know the time")
        goal_extractor = GoalExtractor(client=client)
        goal: str = goal_extractor.extract(messages)
        expected: str = "time"
        self.assertIn(expected, goal)
