import asyncio
import os
import unittest
import pandas as pd

from typing import List

from yaaf.components.agents.artefacts import ArtefactStorage
from yaaf.components.agents.sql_agent import SqlAgent
from yaaf.components.client import OllamaClient
from yaaf.components.data_types import Messages, Note
from yaaf.components.sources.sqlite_source import SqliteSource

_path = os.path.dirname(os.path.abspath(__file__))

sqlite_source = SqliteSource(
    name="London Archaeological Data",
    db_path="../data/london_archaeological_data.db",
)
sqlite_source.ingest(
    df=pd.read_csv(os.path.join(_path, "../data/london_archaeological_data.csv")),
    table_name="archaeological_findings",
)


class TestSqlAgent(unittest.TestCase):
    def test_simple_output(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.4,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance(
            "what are the most common types of finds in the dataset?"
        )
        notes: List[Note] = []
        agent = SqlAgent(client, source=sqlite_source)
        answer = asyncio.run(
            agent.query(
                messages=messages,
                notes=notes,
            )
        )
        storage = ArtefactStorage()
        artefact = storage.retrieve_first_from_utterance_string(answer)
        expected = "Archaeological Priority Area - Tier II"
        print(artefact.data.to_markdown())
        self.assertIn(expected, artefact.data.to_markdown(index=False))
