import logging
from typing import Optional, List, TYPE_CHECKING

from yaaaf.components.data_types import Note

if TYPE_CHECKING:
    from yaaaf.components.data_types import Messages, Utterance, ClientResponse
    from yaaaf.components.agents.artefacts import Artefact

_logger = logging.getLogger(__name__)


def get_agent_name_from_class(agent_class) -> str:
    """Get agent name from class - used by both get_name() and orchestrator builder."""
    return agent_class.__name__.lower()


class BaseAgent:
    def __init__(self):
        self._budget = 2  # Default budget for most agents
        self._original_budget = 2  # Keep track of original budget for reset
        self._artefact_extractor = None  # Will be set by subclasses that need it

    async def query(
        self, messages: "Messages", notes: Optional[List[Note]] = None
    ) -> str:
        pass

    def get_name(self) -> str:
        return get_agent_name_from_class(self.__class__)

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "Base agent with no specific functionality"

    def get_description(self) -> str:
        return f"{self.get_info()}. This is just a Base agent. All it does is to say 'Unknown agent'. Budget: {self._budget} calls."

    def get_budget(self) -> int:
        """Get the current budget (remaining calls) for this agent."""
        return self._budget

    def consume_budget(self) -> bool:
        """Consume one budget token. Returns True if budget was available, False if exhausted."""
        if self._budget > 0:
            self._budget -= 1
            return True
        return False

    def reset_budget(self) -> None:
        """Reset budget to original value for a new query."""
        self._budget = self._original_budget

    def set_budget(self, budget: int) -> None:
        """Set the budget for this agent."""
        self._budget = budget
        self._original_budget = budget

    def get_opening_tag(self) -> str:
        return f"<{self.get_name()}>"

    def get_closing_tag(self) -> str:
        return f"</{self.get_name()}>"

    def is_complete(self, answer: str) -> bool:
        if any(tag in answer for tag in self._completing_tags):
            return True

        return False

    def _add_internal_message(
        self, message: str, notes: Optional[List[Note]], prefix: str = "Message"
    ):
        """Helper to add internal messages to notes"""
        if notes is not None:
            internal_note = Note(
                message=f"[{prefix}] {message}",
                artefact_id=None,
                agent_name=self.get_name(),
                model_name=getattr(getattr(self, "_client", None), "model", None),
                internal=True,
            )
            notes.append(internal_note)

    async def _try_extract_artefacts_from_notes(
        self,
        artefact_list: List["Artefact"],
        last_utterance: "Utterance",
        notes: Optional[List[Note]],
    ) -> List["Artefact"]:
        """
        Try to extract relevant artefacts from conversation notes when none are provided.

        Args:
            artefact_list: Current artefact list (should be empty when this is called)
            last_utterance: The utterance to find artefacts for
            notes: Conversation notes that may contain artefacts

        Returns:
            Updated artefact list with extracted artefacts
        """
        if not artefact_list and notes and self._artefact_extractor:
            _logger.info("No artefacts in utterance, trying to extract from notes")
            extracted_artefact_ids = await self._artefact_extractor.extract(
                last_utterance.content, notes
            )
            if extracted_artefact_ids:
                extracted_artefacts = self._artefact_extractor.get_artefacts_by_ids(
                    extracted_artefact_ids
                )
                _logger.info(
                    f"Found {len(extracted_artefacts)} relevant artefacts from notes"
                )

                # Add internal note about auto-extracted artefacts
                self._add_internal_message(
                    f"Auto-extracted {len(extracted_artefacts)} relevant artefacts from conversation history: {extracted_artefact_ids}",
                    notes,
                    "Artefact Extraction",
                )
                return extracted_artefacts

        return artefact_list

    def _create_thinking_artifact(
        self, response: "ClientResponse", notes: Optional[List[Note]]
    ) -> Optional[str]:
        """
        Create a thinking artifact from the response if thinking content is present.

        Args:
            response: The ClientResponse containing potential thinking content
            notes: Optional notes list to append thinking note to

        Returns:
            Optional artifact reference string if thinking artifact was created
        """
        if not response.thinking_content:
            return None

        # Import here to avoid circular imports
        from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
        from yaaaf.components.agents.hash_utils import create_hash

        # Get or initialize storage
        storage = getattr(self, "_storage", None)
        if storage is None:
            storage = ArtefactStorage()

        # Create hash for thinking content
        thinking_id = create_hash(
            f"thinking_{self.get_name()}_{response.thinking_content}"
        )

        # Store the thinking artifact
        storage.store_artefact(
            thinking_id,
            Artefact(
                type=Artefact.Types.THINKING,
                description=f"Thinking process from {self.get_name()}",
                code=response.thinking_content,
                id=thinking_id,
            ),
        )

        # Add note about thinking artifact
        if notes is not None:
            model_name = getattr(getattr(self, "_client", None), "model", None)
            note = Note(
                message=f"[Thinking] Created thinking artifact: {thinking_id}",
                artefact_id=thinking_id,
                agent_name=self.get_name(),
                model_name=model_name,
                internal=True,
            )
            notes.append(note)

        return f"<artefact type='thinking'>{thinking_id}</artefact>"

    def _process_client_response(
        self, response: "ClientResponse", notes: Optional[List[Note]] = None
    ) -> tuple[str, Optional[str]]:
        """
        Process a client response to extract thinking artifacts and return clean message.

        Args:
            response: The ClientResponse from the client
            notes: Optional notes list to append thinking note to

        Returns:
            Tuple of (clean_message, thinking_artifact_ref)
        """
        thinking_artifact_ref = self._create_thinking_artifact(response, notes)
        return response.message, thinking_artifact_ref
