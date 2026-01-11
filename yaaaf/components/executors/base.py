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

    async def prepare_context(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> Dict[str, Any]:
        """Prepare execution context with artifact resolution.

        Default implementation extracts and resolves artifacts from messages.
        Subclasses can override to add additional context, calling super() first.

        Args:
            messages: The conversation messages
            notes: Optional list of notes containing artifacts

        Returns:
            A dictionary containing the prepared context with 'artifacts' key
        """
        artifacts = self.extract_artifacts_from_messages(messages, notes)
        return {
            "artifacts": artifacts,
            "messages": messages,
            "notes": notes or [],
        }

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
        """Extract artifacts from messages, searching assistant messages first.

        This method searches for artifacts in the message history. After the
        workflow executor fix, only DAG-specified input artifacts appear as
        assistant messages, so agents receive exactly the right artifacts.

        Search order:
        1. Assistant messages in reverse order (DAG inputs)
        2. Notes in reverse order (if provided)

        Args:
            messages: The conversation messages (should contain only user context
                     and DAG input artifacts as assistant messages)
            notes: Optional notes to search if no artifacts found in messages

        Returns:
            List of extracted artifacts
        """
        from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content

        artefact_list = []

        # Search ALL assistant messages - these are DAG inputs
        # Collect artifacts from every assistant message, not just the first one
        if messages.utterances:
            for i, utterance in enumerate(messages.utterances):
                if utterance.role == "assistant":
                    artefacts = get_artefacts_from_utterance_content(utterance.content)
                    if artefacts:
                        artefact_list.extend(artefacts)
                        # Log artifact details with message index for debugging
                        artifact_info = ", ".join([f"{a.type}:{a.id[:8]}..." for a in artefacts])
                        _logger.info(f"Extracted {len(artefacts)} artifacts from DAG input #{i}: [{artifact_info}]")

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
            _logger.debug("No artifacts found in messages or notes")

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

    def is_mutation_operation(self, instruction: str) -> bool:
        """Check if this operation modifies data/files vs read-only.

        Override for executors with both read and write operations.
        Used to filter which results appear in the final combined artifact.
        Read-only results (like file views) are excluded from final output.

        Args:
            instruction: The instruction being executed

        Returns:
            True if this operation modifies data (default), False if read-only.
        """
        return True
