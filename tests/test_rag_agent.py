import os
import unittest

from typing import List

from src.components.agents.rag_agent import RAGAgent
from src.components.client import OllamaClient
from src.components.data_types import Messages
from src.components.sources.rag_source import RAGSource

_path = os.path.dirname(os.path.abspath(__file__))
_source = RAGSource("A wiki page about archaeology")
with open(os.path.join(_path, "../data", "Archaeology - Wikipedia.html"), "r") as f:
    _text = f.read()
_chunk_size = 1000
_overlap = 100
[
    _source.add_text(_text[offset : offset + _chunk_size + _overlap])
    for offset in range(0, len(_text), _chunk_size - _overlap)
]


class TestSqlAgent(unittest.TestCase):
    def test_single_source(self):
        client = OllamaClient(
            model="gemma3:4b",
            temperature=0.4,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "What constitutes an excavation priority area in archaeology?"
        )
        message_queue: List[str] = []
        agent = RAGAgent(client, sources=[_source])
        answer = agent.query(
            messages=messages,
            message_queue=message_queue,
        )
        expected = "excavation"
        self.assertIn(expected, answer)
