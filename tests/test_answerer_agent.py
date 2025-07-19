import asyncio
import os
import unittest
import pandas as pd

from typing import List

from yaaaf.components.agents.answerer_agent import AnswererAgent
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages, Note


class TestAnswererAgent(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.4,
            max_tokens=1000,
        )
        self.agent = AnswererAgent(self.client)
        self.storage = ArtefactStorage()

    def test_process_artifacts(self):
        """Test the artifact processing functionality."""
        # Create sample artifacts
        df1 = pd.DataFrame({
            "product": ["Widget A", "Widget B"],
            "sales": [100, 150],
            "source": ["Database", "Database"]
        })
        
        df2 = pd.DataFrame({
            "search_result": ["AI trends increasing", "Market growing rapidly"],
            "url": ["example.com", "news.com"]
        })
        
        artifacts = [
            Artefact(
                type=Artefact.Types.TABLE,
                description="Sales data from SQL query",
                data=df1,
                id="test_artifact_1"
            ),
            Artefact(
                type=Artefact.Types.TABLE,
                description="Web search results about AI trends",
                data=df2,
                id="test_artifact_2"
            )
        ]
        
        result = self.agent._process_artifacts(artifacts)
        
        # Check that the result contains information from both artifacts
        self.assertIn("Artifact 1", result)
        self.assertIn("Artifact 2", result)
        self.assertIn("Sales data from SQL query", result)
        self.assertIn("Web search results about AI trends", result)
        self.assertIn("Widget A", result)
        self.assertIn("AI trends increasing", result)

    def test_validate_output_table(self):
        """Test the output table validation."""
        # Valid table
        valid_df = pd.DataFrame({
            "paragraph": ["Test paragraph 1", "Test paragraph 2"],
            "source": ["Source 1", "Source 2"]
        })
        self.assertTrue(self.agent._validate_output_table(valid_df))
        
        # Invalid table - wrong columns
        invalid_df = pd.DataFrame({
            "text": ["Test paragraph 1"],
            "reference": ["Source 1"]
        })
        self.assertFalse(self.agent._validate_output_table(invalid_df))
        
        # Invalid table - too many columns
        invalid_df2 = pd.DataFrame({
            "paragraph": ["Test paragraph 1"],
            "source": ["Source 1"],
            "extra": ["Extra data"]
        })
        self.assertFalse(self.agent._validate_output_table(invalid_df2))

    def test_agent_with_multiple_artifacts(self):
        """Test that the agent can handle multiple artifacts in input."""
        # Create and store test artifacts
        df1 = pd.DataFrame({
            "metric": ["Revenue", "Users"],
            "value": [50000, 1200],
            "period": ["Q3", "Q3"]
        })
        
        df2 = pd.DataFrame({
            "insight": ["Market growing", "Competition increasing"],
            "source": ["Industry Report", "Market Analysis"]
        })
        
        artifact1 = Artefact(
            type=Artefact.Types.TABLE,
            description="Company performance metrics",
            data=df1,
            id="perf_metrics_123"
        )
        
        artifact2 = Artefact(
            type=Artefact.Types.TABLE,
            description="Market research findings",
            data=df2,
            id="market_research_456"
        )
        
        self.storage.store_artefact("perf_metrics_123", artifact1)
        self.storage.store_artefact("market_research_456", artifact2)
        
        # Create a message with multiple artifact references
        user_message = (
            "Please analyze these data sources and provide insights: "
            "<artefact type='table'>perf_metrics_123</artefact> "
            "<artefact type='table'>market_research_456</artefact>"
        )
        
        messages = Messages().add_user_utterance(user_message)
        notes: List[Note] = []
        
        # Test artifact extraction
        artifacts = get_artefacts_from_utterance_content(user_message)
        self.assertEqual(len(artifacts), 2)
        self.assertEqual(artifacts[0].id, "perf_metrics_123")
        self.assertEqual(artifacts[1].id, "market_research_456")
        
        # Test artifact processing
        processed_content = self.agent._process_artifacts(artifacts)
        self.assertIn("Company performance metrics", processed_content)
        self.assertIn("Market research findings", processed_content)
        self.assertIn("Revenue", processed_content)
        self.assertIn("Market growing", processed_content)

    def test_agent_info_methods(self):
        """Test the agent's information methods."""
        info = self.agent.get_info()
        self.assertIn("synthesizes information", info.lower())
        self.assertIn("multiple artifacts", info.lower())
        
        description = self.agent.get_description()
        self.assertIn("Answerer agent", description)
        self.assertIn("paragraph", description)
        self.assertIn("source", description)


if __name__ == "__main__":
    unittest.main()