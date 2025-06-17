from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.agents.reflection_agent import ReflectionAgent
from yaaaf.components.agents.reviewer_agent import ReviewerAgent
from yaaaf.components.agents.sql_agent import SqlAgent
from yaaaf.components.agents.url_reviewer_agent import UrlReviewerAgent
from yaaaf.components.agents.visualization_agent import VisualizationAgent
from yaaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.sources.sqlite_source import SqliteSource
from yaaaf.server.config import Settings


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
            elif agent_name != "sql":
                orchestrator.subscribe_agent(
                    self._agents_map[agent_name](client=client)
                )
        return orchestrator
