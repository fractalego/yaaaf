from typing import List

from yaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaf.components.agents.reflection_agent import ReflectionAgent
from yaaf.components.agents.reviewer_agent import ReviewerAgent
from yaaf.components.agents.sql_agent import SqlAgent
from yaaf.components.agents.url_reviewer_agent import UrlReviewerAgent
from yaaf.components.agents.visualization_agent import VisualizationAgent
from yaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaf.components.client import OllamaClient
from yaaf.components.sources.sqlite_source import SqliteSource
from yaaf.server.config import Settings


class OrchestratorBuilder:
    def __init__(self, config: Settings):
        self.config = config
        self._agents_map = {
            "reflection": ReflectionAgent,
            "visualization": VisualizationAgent,
            "sql": SqlAgent,
            "reviewer": ReviewerAgent,
            "websearch": DuckDuckGoSearchAgent,
            "url_reviewer": UrlReviewerAgent,
        }

    def build(self):
        client = OllamaClient(
            model=self.config.client.model,
            temperature=self.config.client.temperature,
            max_tokens=self.config.client.max_tokens,
        )
        source = None
        if len(self.config.sources) > 0:
            source = self.config.sources[0]
            sqlite_source = SqliteSource(
                name=source.name,
                db_path=source.path,
            )
        orchestrator = OrchestratorAgent(client)
        for agent_name in self.config.agents:
            if agent_name not in self._agents_map:
                raise ValueError(f"Agent '{agent_name}' is not recognized.")
            if agent_name == "sql" and source is not None:
                orchestrator.subscribe_agent(
                    self._agents_map[agent_name](client=client, source=sqlite_source)
                )
            else:
                orchestrator.subscribe_agent(
                    self._agents_map[agent_name](client=client)
                )
        return orchestrator
