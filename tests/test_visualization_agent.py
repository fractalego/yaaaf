import unittest
from typing import List

from src.components.client import OllamaClient
from src.components.data_types import Messages
from src.components.agents.visualization_agent import VisualizationAgent


class TestVisualizationAgent(unittest.TestCase):
    def test_simple_output(self):
        client = OllamaClient(
            model="gemma3:4b",
            temperature=0.7,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "Create a plot of the first 100 prime numbers"
        )
        message_queue: List[str] = []
        agent = VisualizationAgent(client)
        answer = agent.query(
            messages=messages,
            message_queue=message_queue,
        )
        print(agent.clean_answer(answer))
        expected = "![Image]("
        self.assertIn(expected, answer)
