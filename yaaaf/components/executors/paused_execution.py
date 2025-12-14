"""Classes for handling paused workflow execution when user input is required."""

import logging
from typing import Dict, Optional
from dataclasses import dataclass
from yaaaf.components.data_types import Messages

_logger = logging.getLogger(__name__)


@dataclass
class PausedExecutionState:
    """State of a paused workflow execution waiting for user input.

    This class stores all necessary information to resume execution
    after receiving user input.
    """

    # Execution identification
    stream_id: str

    # Original request context
    original_messages: Messages

    # Plan execution state
    yaml_plan: str
    completed_assets: Dict[str, str]  # asset_name -> result_string
    current_asset: str  # The user_input asset that paused
    next_asset_index: int  # Index in execution order to resume from

    # User input context
    question_asked: str
    user_input_messages: Messages  # Messages that were passed to UserInputAgent

    # Additional context
    notes: list  # Reference to notes list for continued logging

    def __repr__(self) -> str:
        return (
            f"PausedExecutionState(stream_id={self.stream_id}, "
            f"current_asset={self.current_asset}, "
            f"completed={len(self.completed_assets)}, "
            f"question='{self.question_asked[:50]}...')"
        )


class PausedExecutionException(Exception):
    """Exception raised when workflow execution pauses for user input.

    This exception carries the execution state so it can be resumed
    after the user provides their response.
    """

    def __init__(self, state: PausedExecutionState):
        """Initialize with paused execution state.

        Args:
            state: The state of the paused execution
        """
        self.state = state
        super().__init__(
            f"Execution paused waiting for user input: {state.question_asked}"
        )
        _logger.info(f"Execution paused for stream {state.stream_id}: {state.question_asked}")

    def get_state(self) -> PausedExecutionState:
        """Get the paused execution state."""
        return self.state
