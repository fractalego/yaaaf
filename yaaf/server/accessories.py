from typing import Dict, List
from yaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaf.components.client import OllamaClient

_stream_id_to_messages: Dict[str, List[str]] = {}
_client = OllamaClient(
    model="qwen2.5:32b",
    temperature=0.7,
    max_tokens=100,
)


def do_compute(stream_id, messages):
    message_queue: List[str] = []
    _stream_id_to_messages[stream_id] = message_queue
    orchestrator = OrchestratorAgent(_client)
    orchestrator.query(messages=messages, message_queue=message_queue)


def get_utterances(stream_id):
    return _stream_id_to_messages[stream_id]