import logging
import os
from typing import Dict, List
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.data_types import Note
from yaaaf.components.safety_filter import SafetyFilter
from yaaaf.components.client import OllamaConnectionError, OllamaResponseError
from yaaaf.server.config import get_config

_path = os.path.dirname(os.path.realpath(__file__))
_logger = logging.getLogger(__name__)
_stream_id_to_messages: Dict[str, List[Note]] = {}


async def do_compute(stream_id, messages, orchestrator: OrchestratorAgent):
    try:
        notes: List[Note] = []
        _stream_id_to_messages[stream_id] = notes

        # Apply safety filter
        config = get_config()
        safety_filter = SafetyFilter(config.safety_filter)

        if not safety_filter.is_safe(messages):
            # Add safety message to notes and return early
            safety_note = Note(
                message=safety_filter.get_safety_message(),
                artefact_id=None,
                agent_name="system",
            )
            notes.append(safety_note)
            _logger.info(f"Query blocked by safety filter for stream {stream_id}")
            return

        await orchestrator.query(messages=messages, notes=notes)
    except OllamaConnectionError as e:
        error_message = f"🔌 **Connection Error**: {e}"
        _logger.error(
            f"Accessories: Ollama connection failed for stream {stream_id}: {e}"
        )

        # Create user-friendly error note for frontend
        error_note = Note(
            message=error_message,
            artefact_id=None,
            agent_name="system",
            model_name=None,
        )
        if stream_id in _stream_id_to_messages:
            _stream_id_to_messages[stream_id].append(error_note)

        # Don't re-raise to prevent server error; error is already in notes

    except OllamaResponseError as e:
        error_message = f"⚠️ **Ollama Error**: {e}"
        _logger.error(f"Accessories: Ollama response error for stream {stream_id}: {e}")

        # Create user-friendly error note for frontend
        error_note = Note(
            message=error_message,
            artefact_id=None,
            agent_name="system",
            model_name=None,
        )
        if stream_id in _stream_id_to_messages:
            _stream_id_to_messages[stream_id].append(error_note)

        # Don't re-raise to prevent server error; error is already in notes

    except Exception as e:
        error_message = f"❌ **System Error**: An unexpected error occurred: {e}"
        _logger.error(f"Accessories: Failed to compute for stream {stream_id}: {e}")

        # Store error message in notes for frontend
        error_note = Note(
            message=error_message,
            artefact_id=None,
            agent_name="system",
            model_name=None,
        )
        if stream_id in _stream_id_to_messages:
            _stream_id_to_messages[stream_id].append(error_note)

        # Don't re-raise to prevent server error; error is already in notes


def get_utterances(stream_id):
    try:
        return _stream_id_to_messages[stream_id]
    except KeyError as e:
        _logger.error(f"Accessories: Stream ID {stream_id} not found in messages: {e}")
        return []
    except Exception as e:
        _logger.error(
            f"Accessories: Failed to get utterances for stream {stream_id}: {e}"
        )
        raise
