import unittest
from pprint import pprint

from src.components.agents.orchestrator_agent import OrchestratorAgent
from src.components.agents.sql_agent import SqlAgent
from src.components.agents.visualization_agent import VisualizationAgent
from src.components.client import OllamaClient
from src.components.data_types import Messages
from src.components.agents.reflection_agent import ReflectionAgent
from tests.test_sql_agent import sqlite_source

text_client = OllamaClient(
    model="llama3.1:8b",
    temperature=0.4,
    max_tokens=100,
)
code_client = OllamaClient(
    model="llama3.1:8b",
    temperature=0.4,
    max_tokens=1000,
)
agent = OrchestratorAgent(client=text_client)
agent.subscribe_agent(ReflectionAgent(client=text_client))
agent.subscribe_agent(VisualizationAgent(client=text_client))
agent.subscribe_agent(SqlAgent(client=code_client, source=sqlite_source))


class TestOrchestratorAgent(unittest.TestCase):
    def test_query1(self):
        message_queue: list[str] = []
        messages = Messages().add_user_utterance(
            "How many archaeological findings are there in the dataset?"
        )
        answer = agent.query(
            messages=messages,
            message_queue=message_queue,
        )
        pprint(message_queue)
        expected = "1015"
        self.assertIn(expected, "\n".join(message_queue))

    def test_query2(self):
        message_queue: list[str] = []
        messages = Messages().add_user_utterance(
            "What is the most common archeological finding in the SQL dataset provided?"
        )
        answer = agent.query(
            messages=messages,
            message_queue=message_queue,
        )
        pprint(message_queue)
        print(answer)
        expected = "prehistoric deposits"
        self.assertIn(expected, answer.lower())
