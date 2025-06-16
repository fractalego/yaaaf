import os
from typing import Dict, List
from yaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaf.components.data_types import Note

_path = os.path.dirname(os.path.realpath(__file__))
_stream_id_to_messages: Dict[str, List[Note]] = {}


async def do_compute(stream_id, messages, orchestrator: OrchestratorAgent):
    notes: List[Note] = []
    _stream_id_to_messages[stream_id] = notes
    await orchestrator.query(messages=messages, notes=notes)


def get_utterances(stream_id):
    return _stream_id_to_messages[stream_id]