import logging
import os
from typing import Dict, List, Optional
from yaaaf.components.agents.plan_driven_orchestrator_agent import OrchestratorAgent
from yaaaf.components.data_types import Note
from yaaaf.components.safety_filter import SafetyFilter
from yaaaf.components.client import OllamaConnectionError, OllamaResponseError
from yaaaf.components.executors.paused_execution import (
    PausedExecutionException,
    PausedExecutionState,
)
from yaaaf.server.config import get_config

_path = os.path.dirname(os.path.realpath(__file__))
_logger = logging.getLogger(__name__)
_stream_id_to_messages: Dict[str, List[Note]] = {}
_stream_id_to_paused_state: Dict[str, PausedExecutionState] = {}


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

    except PausedExecutionException as e:
        # Execution paused for user input - keep stream active
        _logger.info(
            f"Execution paused for stream {stream_id}, waiting for user input"
        )

        # Keep stream active but update status
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = True
            _stream_id_to_status[stream_id].current_agent = "Waiting for user input"

        # Note has already been added by orchestrator
        _logger.info(f"Stream {stream_id} is now waiting for user input")

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


def save_paused_state(stream_id: str, state: PausedExecutionState):
    """Save paused execution state for later resumption.

    Args:
        stream_id: The stream identifier
        state: The paused execution state to save
    """
    try:
        _stream_id_to_paused_state[stream_id] = state
        _logger.info(f"Saved paused state for stream {stream_id}: {state}")
    except Exception as e:
        _logger.error(f"Accessories: Failed to save paused state for stream {stream_id}: {e}")


def get_paused_state(stream_id: str) -> Optional[PausedExecutionState]:
    """Get the paused execution state for a stream.

    Args:
        stream_id: The stream identifier

    Returns:
        The paused execution state, or None if not found
    """
    try:
        return _stream_id_to_paused_state.get(stream_id)
    except Exception as e:
        _logger.error(f"Accessories: Failed to get paused state for stream {stream_id}: {e}")
        return None


def clear_paused_state(stream_id: str):
    """Clear the paused execution state for a stream.

    Args:
        stream_id: The stream identifier
    """
    try:
        if stream_id in _stream_id_to_paused_state:
            del _stream_id_to_paused_state[stream_id]
            _logger.info(f"Cleared paused state for stream {stream_id}")
    except Exception as e:
        _logger.error(f"Accessories: Failed to clear paused state for stream {stream_id}: {e}")


async def resume_paused_execution(stream_id: str, user_response: str, orchestrator: OrchestratorAgent):
    """Resume a paused execution with user's response.

    Args:
        stream_id: The stream identifier
        user_response: The user's response to the question
        orchestrator: The orchestrator agent instance
    """
    try:
        # Get paused state
        state = get_paused_state(stream_id)
        if not state:
            _logger.error(f"No paused state found for stream {stream_id}")
            raise ValueError(f"No paused execution found for stream {stream_id}")

        _logger.info(f"Resuming execution for stream {stream_id} with user response: {user_response[:100]}")

        # Get notes for this stream
        notes = _stream_id_to_messages.get(stream_id, [])

        # Update stream status
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = True
            _stream_id_to_status[stream_id].current_agent = "Resuming execution"

        # Create a new workflow executor from the saved state
        from yaaaf.components.executors.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor(
            yaml_plan=state.yaml_plan,
            agents=orchestrator.agents,
            notes=state.notes,
            stream_id=stream_id,
            original_messages=state.original_messages,
        )

        # Resume execution with user's response
        result = await executor.resume_from_paused_state(state, user_response)

        # Add result to notes
        if result:
            from yaaaf.components.data_types import Note

            result_string = str(result.code) if hasattr(result, "code") else str(result)
            result_note = Note(
                message=result_string,
                artefact_id=None,
                agent_name="workflow",
                model_name=None,
            )
            notes.append(result_note)
            _logger.info(f"Added final result to notes for stream {stream_id}")

        # Clear paused state
        clear_paused_state(stream_id)

        # Mark stream as completed
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = False
            _stream_id_to_status[stream_id].current_agent = ""

        _logger.info(f"Successfully resumed and completed execution for stream {stream_id}")

    except PausedExecutionException as e:
        # Execution paused again (nested user input)
        _logger.info(
            f"Execution paused again for stream {stream_id}, waiting for another user input"
        )

        # Keep stream active
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = True
            _stream_id_to_status[stream_id].current_agent = "Waiting for user input"

    except Exception as e:
        error_message = f"❌ **Resume Error**: Failed to resume execution: {e}\n\n<taskcompleted/>"
        _logger.error(f"Accessories: Failed to resume execution for stream {stream_id}: {e}")

        # Add error to notes
        notes = _stream_id_to_messages.get(stream_id, [])
        if notes is not None:
            from yaaaf.components.data_types import Note

            error_note = Note(
                message=error_message,
                artefact_id=None,
                agent_name="system",
                model_name=None,
            )
            notes.append(error_note)

        # Clear paused state and mark stream as completed
        clear_paused_state(stream_id)
        if stream_id in _stream_id_to_status:
            _stream_id_to_status[stream_id].is_active = False
            _stream_id_to_status[stream_id].current_agent = ""
