import asyncio
import unittest
from typing import List

from yaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaf.components.client import OllamaClient
from yaaf.components.data_types import Messages, Note
from yaaf.components.agents.visualization_agent import VisualizationAgent


class TestVisualizationAgent(unittest.TestCase):
    def test_simple_output(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.7,
            max_tokens=1000,
        )
        hash_key = "12345"
        messages = Messages().add_user_utterance(
            f"Create a plot of the first 100 prime numbers through a visualization. A dummy artefact is <artefact>{hash_key}</artefact>."
        )
        notes: List[Note] = []
        storage = ArtefactStorage()
        artefact = Artefact(
            model=None,
            data=None,
            code=None,
            description="Test artefact",
            image=None,
            type="test",
            id="test_id",
        )
        storage.store_artefact(hash_key, artefact)
        agent = VisualizationAgent(client)
        answer = asyncio.run(
            agent.query(
                messages=messages,
                notes=notes,
            )
        )
        expected = "<artefact type='image'>"
        print(answer)
        self.assertIn(expected, answer)
