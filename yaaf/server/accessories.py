import os
from typing import Dict, List
from yaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaf.components.agents.reflection_agent import ReflectionAgent
from yaaf.components.agents.reviewer_agent import ReviewerAgent
from yaaf.components.agents.sql_agent import SqlAgent
from yaaf.components.agents.visualization_agent import VisualizationAgent
from yaaf.components.client import OllamaClient
from yaaf.components.sources.sqlite_source import SqliteSource

_path = os.path.dirname(os.path.realpath(__file__))
_stream_id_to_messages: Dict[str, List[str]] = {}

_client = OllamaClient(
    model="qwen2.5:32b",
    temperature=0.7,
    max_tokens=100,
)
_sqlite_source = SqliteSource(
    name="London Archaeological Data",
    db_path=os.path.join(_path, "../../data/london_archaeological_data.db"),
)
_orchestrator = OrchestratorAgent(_client)
_orchestrator.subscribe_agent(ReflectionAgent(client=_client))
_orchestrator.subscribe_agent(VisualizationAgent(client=_client))
_orchestrator.subscribe_agent(SqlAgent(client=_client, source=_sqlite_source))
_orchestrator.subscribe_agent(ReviewerAgent(client=_client))


async def do_compute(stream_id, messages):
    message_queue: List[str] = []
    _stream_id_to_messages[stream_id] = message_queue
    await _orchestrator.query(messages=messages, message_queue=message_queue)


def get_utterances(stream_id):
    return _stream_id_to_messages[stream_id]
