import os
from typing import List
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.agents.reflection_agent import ReflectionAgent
from yaaaf.components.agents.reviewer_agent import ReviewerAgent
from yaaaf.components.agents.sql_agent import SqlAgent
from yaaaf.components.agents.rag_agent import RAGAgent
from yaaaf.components.agents.url_reviewer_agent import UrlReviewerAgent
from yaaaf.components.agents.visualization_agent import VisualizationAgent
from yaaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.sources.sqlite_source import SqliteSource
from yaaaf.components.sources.rag_source import RAGSource
from yaaaf.server.config import Settings


class OrchestratorBuilder:
    def __init__(self, config: Settings):
        self.config = config
        self._agents_map = {
            "reflection": ReflectionAgent,
            "visualization": VisualizationAgent,
            "sql": SqlAgent,
            "rag": RAGAgent,
            "reviewer": ReviewerAgent,
            "websearch": DuckDuckGoSearchAgent,
            "url_reviewer": UrlReviewerAgent,
        }

    def _load_text_from_file(self, file_path: str) -> str:
        """Load text content from a file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()

    def _create_rag_sources(self) -> List[RAGSource]:
        """Create RAG sources from text-type sources in config."""
        rag_sources = []
        for source_config in self.config.sources:
            if source_config.type == "text":
                description = getattr(source_config, "description", source_config.name)
                rag_source = RAGSource(
                    description=description, source_path=source_config.path
                )

                # Load text content from file or directory
                if os.path.isfile(source_config.path):
                    # Single file
                    text_content = self._load_text_from_file(source_config.path)
                    rag_source.add_text(text_content)
                elif os.path.isdir(source_config.path):
                    # Directory of files
                    for filename in os.listdir(source_config.path):
                        file_path = os.path.join(source_config.path, filename)
                        if os.path.isfile(file_path) and filename.lower().endswith(
                            (".txt", ".md", ".html", ".htm")
                        ):
                            text_content = self._load_text_from_file(file_path)
                            rag_source.add_text(text_content)

                rag_sources.append(rag_source)
        return rag_sources

    def _get_sqlite_source(self):
        """Get the first SQLite source from config."""
        for source_config in self.config.sources:
            if source_config.type == "sqlite":
                return SqliteSource(
                    name=source_config.name,
                    db_path=source_config.path,
                )
        return None

    def build(self):
        client = OllamaClient(
            model=self.config.client.model,
            temperature=self.config.client.temperature,
            max_tokens=self.config.client.max_tokens,
        )

        # Prepare sources
        sqlite_source = self._get_sqlite_source()
        rag_sources = self._create_rag_sources()

        orchestrator = OrchestratorAgent(client)

        for agent_name in self.config.agents:
            if agent_name not in self._agents_map:
                raise ValueError(f"Agent '{agent_name}' is not recognized.")

            if agent_name == "sql" and sqlite_source is not None:
                orchestrator.subscribe_agent(
                    self._agents_map[agent_name](client=client, source=sqlite_source)
                )
            elif agent_name == "rag" and rag_sources:
                orchestrator.subscribe_agent(
                    self._agents_map[agent_name](client=client, sources=rag_sources)
                )
            elif agent_name not in ["sql", "rag"]:
                orchestrator.subscribe_agent(
                    self._agents_map[agent_name](client=client)
                )

        return orchestrator
