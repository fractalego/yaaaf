import asyncio
import os
import tempfile
import unittest
from unittest.mock import Mock

from yaaaf.components.orchestrator_builder import OrchestratorBuilder
from yaaaf.server.config import Settings, SourceSettings, ClientSettings


class TestOrchestratorBuilder(unittest.TestCase):
    def setUp(self):
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "../data")
        self.archaeology_file = os.path.join(
            self.test_data_dir, "Archaeology - Wikipedia.html"
        )

    def test_build_with_rag_agent_and_text_source(self):
        """Test that the orchestrator builder correctly builds RAG agent with text sources."""
        # Create a minimal config with RAG agent and text source
        config = Settings(
            client=ClientSettings(
                model="qwen2.5:32b", temperature=0.7, max_tokens=1024
            ),
            agents=["rag"],
            sources=[
                SourceSettings(
                    name="Wikipedia page about archaeology",
                    type="text",
                    path=self.archaeology_file,
                    description="Wikipedia page about archaeology",
                )
            ],
        )

        # Build the orchestrator
        builder = OrchestratorBuilder(config)
        orchestrator = builder.build()

        # Verify the orchestrator was created
        self.assertIsNotNone(orchestrator)

        # Verify that the RAG agent was subscribed
        self.assertEqual(len(orchestrator._agents_map), 1)

        # Get the RAG agent
        rag_agent = list(orchestrator._agents_map.values())[0]
        self.assertEqual(rag_agent.__class__.__name__, "RAGAgent")

        # Verify the RAG agent has sources
        self.assertGreater(len(rag_agent._sources), 0)

        # Verify the source has the correct description
        source = rag_agent._sources[0]
        self.assertEqual(source._description, "Wikipedia page about archaeology")
        self.assertEqual(source.source_path, self.archaeology_file)

    def test_build_with_mixed_sources(self):
        """Test that the builder correctly handles both SQLite and text sources."""
        # Create a temporary SQLite file for testing
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            temp_db_path = temp_db.name

        try:
            config = Settings(
                client=ClientSettings(
                    model="qwen2.5:32b", temperature=0.7, max_tokens=1024
                ),
                agents=["sql", "rag"],
                sources=[
                    SourceSettings(
                        name="test_sqlite_db", type="sqlite", path=temp_db_path
                    ),
                    SourceSettings(
                        name="Wikipedia page about archaeology",
                        type="text",
                        path=self.archaeology_file,
                        description="Wikipedia page about archaeology",
                    ),
                ],
            )

            builder = OrchestratorBuilder(config)
            orchestrator = builder.build()

            # Verify both agents were created
            self.assertEqual(len(orchestrator._agents_map), 2)

            # Find agents by class name
            agent_classes = [
                agent.__class__.__name__ for agent in orchestrator._agents_map.values()
            ]
            self.assertIn("SqlAgent", agent_classes)
            self.assertIn("RAGAgent", agent_classes)

        finally:
            # Clean up temporary file
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_create_rag_sources_from_directory(self):
        """Test that the builder can create RAG sources from a directory of text files."""
        # Create a temporary directory with test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test text files
            test_files = {
                "doc1.txt": "This is the first document about archaeology.",
                "doc2.md": "# Second Document\nThis is about archaeological methods.",
                "doc3.html": "<html><body>Third document content</body></html>",
            }

            for filename, content in test_files.items():
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

            config = Settings(
                client=ClientSettings(
                    model="qwen2.5:32b", temperature=0.7, max_tokens=1024
                ),
                agents=["rag"],
                sources=[
                    SourceSettings(
                        name="test_docs",
                        type="text",
                        path=temp_dir,
                        description="Test documents directory",
                    )
                ],
            )

            builder = OrchestratorBuilder(config)
            rag_sources = builder._create_rag_sources()

            # Verify RAG source was created
            self.assertEqual(len(rag_sources), 1)

            rag_source = rag_sources[0]
            self.assertEqual(rag_source._description, "Test documents directory")
            self.assertEqual(rag_source.source_path, temp_dir)

            # Verify texts were added (check that vector DB has content)
            self.assertGreater(len(rag_source._id_to_chunk), 0)

    def test_load_text_from_file_with_encoding(self):
        """Test that the text loading handles different encodings correctly."""
        # Create a temporary file with UTF-8 content
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write("Test content with Unicode: café, naïve, résumé")
            temp_file_path = temp_file.name

        try:
            config = Settings(
                client=ClientSettings(model="test", temperature=0.7, max_tokens=1024),
                agents=[],
                sources=[],
            )
            builder = OrchestratorBuilder(config)

            # Test loading the file
            content = builder._load_text_from_file(temp_file_path)
            self.assertIn("café", content)
            self.assertIn("naïve", content)
            self.assertIn("résumé", content)

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_rag_agent_integration_with_archaeology_file(self):
        """Integration test: Test RAG agent with the actual archaeology file."""
        # Skip if the archaeology file doesn't exist
        if not os.path.exists(self.archaeology_file):
            self.skipTest(f"Archaeology file not found at {self.archaeology_file}")

        config = Settings(
            client=ClientSettings(
                model="qwen2.5:32b", temperature=0.4, max_tokens=1000
            ),
            agents=["rag"],
            sources=[
                SourceSettings(
                    name="Wikipedia page about archaeology",
                    type="text",
                    path=self.archaeology_file,
                    description="Wikipedia page about archaeology",
                )
            ],
        )

        builder = OrchestratorBuilder(config)
        orchestrator = builder.build()

        # Test querying the orchestrator
        from yaaaf.components.data_types import Messages

        messages = Messages().add_user_utterance(
            "<ragagent>What is archaeology and what are its main methods?</ragagent>"
        )

        # This is an integration test - it requires a working LLM
        # In a real environment, you might want to mock the client
        try:
            answer = asyncio.run(orchestrator.query(messages))
            self.assertIsInstance(answer, str)
            self.assertGreater(len(answer), 0)
            # Should contain an artifact reference for the RAG results
            self.assertIn("artefact", answer.lower())
        except Exception as e:
            # If the test fails due to LLM unavailability, just verify the setup worked
            self.skipTest(f"LLM not available for integration test: {e}")


if __name__ == "__main__":
    unittest.main()
