import logging
import os
from typing import Dict, List
from yaaaf.components.agents.plan_driven_orchestrator_agent import OrchestratorAgent
from yaaaf.components.data_types import Note
from yaaaf.components.safety_filter import SafetyFilter
from yaaaf.components.client import OllamaConnectionError, OllamaResponseError
from yaaaf.server.config import get_config

_path = os.path.dirname(os.path.realpath(__file__))
_logger = logging.getLogger(__name__)
_stream_id_to_messages: Dict[str, List[Note]] = {}


# Global status tracking for frontend display
class StreamStatus:
    def __init__(self):
        self.goal: str = ""
        self.current_agent: str = ""
        self.is_active: bool = False


_stream_id_to_status: Dict[str, StreamStatus] = {}


async def do_compute(stream_id, messages, orchestrator: OrchestratorAgent):
    try:
        notes: List[Note] = []
        _stream_id_to_messages[stream_id] = notes

        # Initialize status tracking for this stream
        status = StreamStatus()
        status.is_active = True
        status.current_agent = "orchestrator"
        _stream_id_to_status[stream_id] = status

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

        result = await orchestrator.query(messages=messages, notes=notes, stream_id=stream_id)
        
        if result:
            # Check if the result is an error message (contains <taskcompleted/>)
            if "<taskcompleted/>" in result:
                # This is an error from the @handle_exceptions decorator
                error_note = Note(
                    message=result,
                    artefact_id=None,
                    agent_name="system",
                    model_name=None,
                )
                notes.append(error_note)
                _logger.info(f"Added error message to notes for stream {stream_id}")
            else:
                # This is a successful result - add it to notes for frontend display
                result_note = Note(
                    message=result,
                    artefact_id=None,
                    agent_name="orchestrator",
                    model_name=None,
                )
                notes.append(result_note)
                _logger.info(f"Added successful result to notes for stream {stream_id}")

        # Mark stream as completed
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = False
            _stream_id_to_status[stream_id].current_agent = ""
    except OllamaConnectionError as e:
        error_message = f"🔌 **Connection Error**: {e}\n\n<taskcompleted/>"
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

        # Mark stream as completed
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = False
            _stream_id_to_status[stream_id].current_agent = ""

    except OllamaResponseError as e:
        error_message = f"⚠️ **Ollama Error**: {e}\n\n<taskcompleted/>"
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

        # Mark stream as completed
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = False
            _stream_id_to_status[stream_id].current_agent = ""

    except Exception as e:
        error_message = f"❌ **System Error**: An unexpected error occurred: {e}\n\n<taskcompleted/>"
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

        # Mark stream as completed
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = False
            _stream_id_to_status[stream_id].current_agent = ""


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


def get_stream_status(stream_id):
    """Get the current status of a stream"""
    try:
        return _stream_id_to_status.get(stream_id, None)
    except Exception as e:
        _logger.error(f"Accessories: Failed to get status for stream {stream_id}: {e}")
        return None


def update_stream_status(stream_id, goal: str = None, current_agent: str = None):
    """Update the status of a stream"""
    try:
        if stream_id not in _stream_id_to_status:
            _stream_id_to_status[stream_id] = StreamStatus()

        status = _stream_id_to_status[stream_id]
        if goal is not None:
            status.goal = goal
        if current_agent is not None:
            status.current_agent = current_agent

        _logger.info(
            f"Updated status for stream {stream_id}: goal='{goal}', agent='{current_agent}'"
        )
    except Exception as e:
        _logger.error(
            f"Accessories: Failed to update status for stream {stream_id}: {e}"
        )
