import asyncio
import unittest
from typing import List

from yaaf.components.client import OllamaClient
from yaaf.components.data_types import Messages
from yaaf.components.agents.visualization_agent import VisualizationAgent


class TestVisualizationAgent(unittest.TestCase):
    def test_simple_output(self):
        client = OllamaClient(
            model="gemma3:4b",
            temperature=0.7,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "Create a plot of the first 100 prime numbers through a visualization."
        )
        message_queue: List[str] = []
        agent = VisualizationAgent(client)
        answer = asyncio.run(
            agent.query(
                messages=messages,
                message_queue=message_queue,
            )
        )
        print(agent.clean_answer(answer))
        expected = "![Image]("
        self.assertIn(expected, answer)
