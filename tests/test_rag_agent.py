import asyncio
import os
import unittest

from typing import List

from yaaf.components.agents.rag_agent import RAGAgent
from yaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaf.components.client import OllamaClient
from yaaf.components.data_types import Messages
from yaaf.components.sources.rag_source import RAGSource

_path = os.path.dirname(os.path.abspath(__file__))
_source = RAGSource(description="A wiki page about archaeology", source_path="wiki/archaeology")
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
        answer = asyncio.run(
            agent.query(
                messages=messages,
                message_queue=message_queue,
            )
        )
        artefacts = get_artefacts_from_utterance_content(answer)
        assert len(artefacts) == 1
        expected = "excavation"
        data = artefacts[0].data.to_markdown()
        self.assertIn(expected, data)
