from abc import ABC, abstractmethod
from typing import Any, Tuple, Optional, Dict, List
import logging

from yaaaf.components.agents.artefacts import Artefact
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class ToolExecutor(ABC):
    """Abstract base class for tool execution.

    This class defines the interface that all tool executors must implement.
    Tool executors handle the specific logic for different types of operations
    like SQL queries, web searches, code execution, etc.
    """

    @abstractmethod
    async def prepare_context(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> Dict[str, Any]:
        """Prepare execution context.

        This method sets up any necessary context for the execution,
        such as loading schemas, extracting artifacts, or setting up
        environment variables.

        Args:
            messages: The conversation messages
            notes: Optional list of notes containing artifacts

        Returns:
            A dictionary containing the prepared context
        """
        pass

    @abstractmethod
    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract the executable instruction from the agent's response.

        This method parses the response to find the specific instruction
        to execute (SQL query, search query, code block, etc.)

        Args:
            response: The agent's response text

        Returns:
            The extracted instruction or None if not found
        """
        pass

    @abstractmethod
    async def execute_operation(
        self, instruction: str, context: Dict[str, Any]
    ) -> Tuple[Any, Optional[str]]:
        """Execute the core operation.

        This method performs the actual execution of the instruction
        using the prepared context.

        Args:
            instruction: The instruction to execute
            context: The prepared context from prepare_context

        Returns:
            A tuple of (result, error_message) where error_message is None on success
        """
        pass

    @abstractmethod
    def validate_result(self, result: Any) -> bool:
        """Validate if the result is successful.

        This method checks whether the execution result is valid
        and can be used to create an artifact.

        Args:
            result: The result from execute_operation

        Returns:
            True if the result is valid, False otherwise
        """
        pass

    def extract_artifacts_from_messages(self, messages: Messages, notes: Optional[List[Note]] = None) -> List[Artefact]:
        """Extract artifacts from messages, searching in reverse order.
        
        This is a common pattern needed by multiple executors. It searches:
        1. Last utterance first
        2. All previous messages in reverse order
        3. Notes in reverse order (if provided)
        
        Args:
            messages: The conversation messages
            notes: Optional notes to search if no artifacts found in messages
            
        Returns:
            List of extracted artifacts
        """
        from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
        
        artefact_list = []
        
        # First check the last utterance for artifacts
        if messages.utterances:
            last_utterance = messages.utterances[-1]
            artefact_list = get_artefacts_from_utterance_content(last_utterance.content)
        
        # If no artifacts found, look through ALL messages in reverse order
        if not artefact_list and messages.utterances:
            for i in range(len(messages.utterances) - 2, -1, -1):  # Start from second-to-last
                utterance = messages.utterances[i]
                artefacts = get_artefacts_from_utterance_content(utterance.content)
                if artefacts:
                    artefact_list = artefacts
                    _logger.info(f"Found {len(artefacts)} artifacts in previous {utterance.role} message")
                    break
        
        # If still no artifacts found, look through notes in reverse order
        if not artefact_list and notes:
            for i in range(len(notes) - 1, -1, -1):
                note = notes[i]
                if note.message:
                    artefacts = get_artefacts_from_utterance_content(note.message)
                    if artefacts:
                        artefact_list = artefacts
                        _logger.info(f"Found {len(artefacts)} artifacts in note from {note.agent_name}")
                        break
        
        if not artefact_list:
            _logger.info("No artifacts found in messages or notes")
            
        return artefact_list

    @abstractmethod
    def transform_to_artifact(
        self, result: Any, instruction: str, artifact_id: str
    ) -> Artefact:
        """Transform result into an Artifact.

        This method converts the execution result into an Artifact
        that can be stored and referenced.

        Args:
            result: The result from execute_operation
            instruction: The original instruction that was executed
            artifact_id: The ID to use for the artifact

        Returns:
            An Artifact object
        """
        pass

    def get_output_tag(self) -> Optional[str]:
        """Get the output tag used to extract instructions.

        Override this method to specify a custom output tag.
        Default implementation returns None.

        Returns:
            The output tag or None
        """
        return None

    def get_feedback_message(self, error: str) -> str:
        """Generate a feedback message for errors.

        Override this method to customize error feedback.

        Args:
            error: The error message

        Returns:
            A formatted feedback message
        """
        return f"Error: {error}. Please correct and try again."
