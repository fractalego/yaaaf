import unittest

from src.components.agents.orchestrator_agent import OrchestratorAgent
from src.components.agents.sql_agent import SqlAgent
from src.components.agents.visualization_agent import VisualizationAgent
from src.components.client import OllamaClient
from src.components.data_types import Messages
from src.components.agents.reflection_agent import ReflectionAgent


class TestOrchestratorAgent(unittest.TestCase):
    def test_simple_output(self):
        text_client = OllamaClient(
            model="gemma3:4b",
            temperature=0.7,
            max_tokens=100,
        )
        code_client = OllamaClient(
            model="gemma3:4b",
            temperature=0.4,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance("How many archaeological findings are there in the dataset and where")
        agent = OrchestratorAgent(client=text_client)
        agent.subscribe_agent(ReflectionAgent(client=text_client))
        agent.subscribe_agent(VisualizationAgent(client=text_client))
        agent.subscribe_agent(SqlAgent(client=code_client))
        answer = agent.query(
            messages=messages,
        )
        expected = "Paris"
        self.assertIn(expected, answer)