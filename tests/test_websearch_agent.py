import asyncio
import unittest

from typing import List

from yaaaf.components.agents.artefacts import ArtefactStorage
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.agents.url_reviewer_agent import UrlReviewerAgent
from yaaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages, Note


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
        notes: List[Note] = []
        agent = DuckDuckGoSearchAgent(client)
        answer = asyncio.run(
            agent.query(
                messages=messages,
                notes=notes,
            )
        )
        storage = ArtefactStorage()
        artefact = storage.retrieve_first_from_utterance_string(answer)
        expected = "wikipedia"
        print(artefact.data.to_markdown())
        self.assertIn(expected, artefact.data.to_markdown(index=False))

    def test_search_and_retrieval(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.4,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "How many people are there in the world?"
        )
        notes: List[Note] = []
        agent = OrchestratorAgent(client=client)
        agent.subscribe_agent(DuckDuckGoSearchAgent(client=client))
        agent.subscribe_agent(UrlReviewerAgent(client=client))
        asyncio.run(
            agent.query(
                messages=messages,
                notes=notes,
            )
        )

        storage = ArtefactStorage()
        artefact = storage.retrieve_from_utterance_string(
            "".join([note.message for note in notes])
        )[-1]
        expected = "population"
        print(artefact.data.to_markdown(index=False))
        self.assertIn(expected, artefact.data.to_markdown(index=False).lower())
