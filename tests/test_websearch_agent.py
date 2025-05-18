import asyncio
import unittest

from typing import List

from yaaf.components.agents.artefacts import ArtefactStorage
from yaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaf.components.client import OllamaClient
from yaaf.components.data_types import Messages


class TestWebSearchAgent(unittest.TestCase):
    def test_simple_search(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.4,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "who is the author of the book 'The Archaeology of Knowledge'?"
        )
        message_queue: List[str] = []
        agent = DuckDuckGoSearchAgent(client)
        answer = asyncio.run(
            agent.query(
                messages=messages,
                message_queue=message_queue,
            )
        )
        storage = ArtefactStorage()
        artefact = storage.retrieve_from_utterance_string(answer)
        expected = "wikipedia"
        print(artefact.data.to_markdown())
        self.assertIn(expected, artefact.data.to_markdown(index=False))