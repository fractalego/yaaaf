import unittest

from src.components.client import OllamaClient
from src.components.data_types import Messages
from src.components.agents.reflection_agent import ReflectionAgent


class TestSelfReflectionAgent(unittest.TestCase):
    def test_simple_output(self):
        client = OllamaClient(
            model="gemma3:4b",
            temperature=0.7,
            max_tokens=100,
        )
        messages = Messages().add_user_utterance("What is the capital of France?")
        answer = ReflectionAgent(client).query(
            messages=messages,
        )
        expected = "Paris"
        self.assertIn(expected, answer)
