import unittest

from src.components.client import OllamaClient
from src.components.data_types import Messages


class TestClients(unittest.TestCase):
    def test_client_initialization(self):
        client = OllamaClient(
            model="qwen2.5-coder:latest",
            temperature=0.7,
            max_tokens=100,
        )
        messages = Messages().add_system_prompt("You only say hello.").add_user_utterance("Hello, how are you?")
        answer = client.predict(
            messages=messages,
            stop_sequences=["<complete/>"]
        )
        expected = "hello"
        self.assertIn(expected, answer.lower())
