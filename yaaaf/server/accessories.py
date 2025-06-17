import logging
import os
from typing import Dict, List
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.data_types import Note

_path = os.path.dirname(os.path.realpath(__file__))
_logger = logging.getLogger(__name__)
_stream_id_to_messages: Dict[str, List[Note]] = {}


async def do_compute(stream_id, messages, orchestrator: OrchestratorAgent):
    try:
        notes: List[Note] = []
        _stream_id_to_messages[stream_id] = notes
        await orchestrator.query(messages=messages, notes=notes)
    except Exception as e:
        _logger.error(f"Accessories: Failed to compute for stream {stream_id}: {e}")
        # Store error message in notes for frontend
        error_note = Note(
            message=f"Error during computation: {e}",
            artefact_id=None,
            agent_name="system"
        )
        if stream_id in _stream_id_to_messages:
            _stream_id_to_messages[stream_id].append(error_note)
        raise


def get_utterances(stream_id):
    try:
        return _stream_id_to_messages[stream_id]
    except KeyError as e:
        _logger.error(f"Accessories: Stream ID {stream_id} not found in messages: {e}")
        return []
    except Exception as e:
        _logger.error(f"Accessories: Failed to get utterances for stream {stream_id}: {e}")
        raise