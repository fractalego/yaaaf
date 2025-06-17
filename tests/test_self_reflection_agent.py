import asyncio
import unittest

from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages
from yaaaf.components.agents.reflection_agent import ReflectionAgent


class TestSelfReflectionAgent(unittest.TestCase):
    def test_simple_output(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.7,
            max_tokens=100,
        )
        messages = Messages().add_user_utterance("What is the capital of France?")
        agent = ReflectionAgent(client)
        answer = asyncio.run(
            agent.query(
                messages=messages,
            )
        )
        expected = ["Paris", "France", "capital of France"]
        print(answer)
        for exp in expected:
            self.assertIn(exp.lower(), answer.lower())
