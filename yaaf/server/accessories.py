import os
from typing import Dict, List
from yaaf.components.agents.orchestrator_agent import OrchestratorAgent

_path = os.path.dirname(os.path.realpath(__file__))
_stream_id_to_messages: Dict[str, List[str]] = {}


async def do_compute(stream_id, messages, orchestrator: OrchestratorAgent):
    message_queue: List[str] = []
    _stream_id_to_messages[stream_id] = message_queue
    await orchestrator.query(messages=messages, message_queue=message_queue)


def get_utterances(stream_id):
    return _stream_id_to_messages[stream_id]