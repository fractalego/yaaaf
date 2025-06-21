import logging
import os
import asyncio
from typing import Dict, List, Set
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.data_types import Note
from yaaaf.components.safety_filter import SafetyFilter
from yaaaf.components.client import OllamaConnectionError, OllamaResponseError
from yaaaf.server.config import get_config

_path = os.path.dirname(os.path.realpath(__file__))
_logger = logging.getLogger(__name__)
_stream_id_to_messages: Dict[str, List[Note]] = {}
_active_streams: Set[str] = set()  # Track active streams
_cancelled_streams: Set[str] = set()  # Track cancelled streams


def register_stream(stream_id: str):
    """Register a new active stream"""
    _active_streams.add(stream_id)
    _cancelled_streams.discard(stream_id)  # Remove from cancelled if it was there
    _logger.info(f"Accessories: Registered active stream {stream_id}")


def cancel_stream(stream_id: str):
    """Mark a stream as cancelled"""
    _cancelled_streams.add(stream_id)
    _active_streams.discard(stream_id)
    _logger.info(f"Accessories: Cancelled stream {stream_id}")


def is_stream_cancelled(stream_id: str) -> bool:
    """Check if a stream has been cancelled"""
    return stream_id in _cancelled_streams


def cleanup_stream(stream_id: str):
    """Clean up stream resources"""
    _active_streams.discard(stream_id)
    _cancelled_streams.discard(stream_id)
    if stream_id in _stream_id_to_messages:
        del _stream_id_to_messages[stream_id]
    _logger.info(f"Accessories: Cleaned up stream {stream_id}")


async def do_compute(stream_id, messages, orchestrator: OrchestratorAgent):
    try:
        register_stream(stream_id)
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

        await orchestrator.query(messages=messages, notes=notes, stream_id=stream_id)
    except asyncio.CancelledError:
        _logger.info(f"Accessories: Stream {stream_id} was cancelled")
        # Add cancellation note
        if stream_id in _stream_id_to_messages:
            cancel_note = Note(
                message="🛑 Task was cancelled because the browser tab was closed.",
                artefact_id=None,
                agent_name="system",
                model_name=None,
            )
            _stream_id_to_messages[stream_id].append(cancel_note)
        raise  # Re-raise to propagate cancellation
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
    finally:
        # Always cleanup stream resources when computation ends
        cleanup_stream(stream_id)


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
