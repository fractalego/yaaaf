from typing import List
import logging

from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note, PromptTemplate
from yaaaf.components.extractors.base_extractor import BaseExtractor
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage

_logger = logging.getLogger(__name__)

artefact_extractor_prompt = PromptTemplate(
    prompt="""
You are an artefact extractor. Your task is to analyze conversation notes and identify the most relevant artefacts for a given instruction.

Given the following instruction and available notes with artefacts, select the most relevant artefact IDs that would be helpful for completing the instruction.

Instruction: {instruction}

Available notes with artefacts:
{notes_with_artefacts}

Please analyze which artefacts would be most useful for the given instruction. Consider:
1. Direct relevance to the instruction topic
2. Data types that match what the instruction needs (tables, models, images, etc.)
3. Recency and quality of the artefacts
4. Context and description match

Return only the artefact IDs (one per line) that are most relevant, in order of relevance:
"""
)


class ArtefactExtractor(BaseExtractor):
    """
    ArtefactExtractor analyzes conversation notes to find the most relevant artefacts
    for a given instruction when no artefacts are explicitly provided.
    """

    _artefact_extractor_prompt: PromptTemplate = artefact_extractor_prompt
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client

    def _format_notes_with_artefacts(self, notes: List[Note]) -> str:
        """Format notes that contain artefacts for the prompt"""
        formatted_notes = []
        for note in notes:
            if note.artefact_id:
                try:
                    artefact = self._storage.retrieve_from_id(note.artefact_id)
                    artefact_desc = f"Artefact ID: {note.artefact_id}\n"
                    artefact_desc += f"Message : {note.message}\n"
                    artefact_desc += f"From agent: {note.agent_name or 'unknown'}\n"
                    artefact_desc += f"Type: {artefact.type or 'unknown'}\n"
                    artefact_desc += f"Description: {artefact.description or artefact.summary or 'No description'}\n"
                    artefact_desc += f"Context: {note.message[:200]}...\n"
                    artefact_desc += f"Agent: {note.agent_name or 'unknown'}\n"
                    formatted_notes.append(artefact_desc)
                except (ValueError, AttributeError) as e:
                    _logger.warning(
                        f"Could not retrieve artefact {note.artefact_id}: {e}"
                    )
                    continue

        return (
            "\n---\n".join(formatted_notes)
            if formatted_notes
            else "No artefacts found in notes."
        )

    async def extract(self, instruction: str, notes: List[Note]) -> List[str]:
        """
        Extract the most relevant artefact IDs for the given instruction from the notes.

        Args:
            instruction: The instruction that needs artefacts
            notes: List of conversation notes that may contain artefacts

        Returns:
            List of artefact IDs ordered by relevance
        """
        if not notes:
            _logger.info("No notes provided for artefact extraction")
            return []

        # Filter notes that have artefacts
        notes_with_artefacts = [note for note in notes if note.artefact_id]

        if not notes_with_artefacts:
            _logger.info("No notes with artefacts found")
            return []

        # Format notes for the prompt
        formatted_notes = self._format_notes_with_artefacts(notes_with_artefacts)

        # Create extraction prompt
        extraction_messages = Messages().add_system_prompt(
            self._artefact_extractor_prompt.complete(
                instruction=instruction, notes_with_artefacts=formatted_notes
            )
        )
        extraction_messages = extraction_messages.add_user_utterance(
            "List the most relevant artefact IDs for this instruction: {instruction}. "
            "This is just a best guess effort, so you MUST provide the IDs no matter what."
        )

        try:
            # Get LLM response
            response = await self._client.predict(extraction_messages)
            answer = response.message

            # Parse artefact IDs from response
            artefact_ids = []
            for line in answer.strip().split("\n"):
                line = line.strip()
                # Handle various formats: "artefact_id", "- artefact_id", "1. artefact_id", etc.
                if (
                    line
                    and not line.startswith("#")
                    and not line.lower().startswith("none")
                ):
                    # Extract artefact ID (remove bullets, numbers, etc.)
                    cleaned_line = line.lstrip("- ").strip()
                    if cleaned_line and cleaned_line in [
                        note.artefact_id for note in notes_with_artefacts
                    ]:
                        artefact_ids.append(cleaned_line)

            _logger.info(
                f"Extracted {len(artefact_ids)} relevant artefact IDs for instruction: {instruction[:50]}..."
            )

            # If no artefacts suggested by LLM, return the latest one from notes
            if not artefact_ids:
                _logger.info(
                    "No artefacts suggested by LLM, returning latest artefact from notes"
                )
                # Sort notes by timestamp (if available) or by order, get the latest
                latest_note = max(
                    notes_with_artefacts,
                    key=lambda n: getattr(n, "timestamp", 0),
                    default=None,
                )
                if latest_note and latest_note.artefact_id:
                    return [latest_note.artefact_id]
                return []

            return artefact_ids[:3]  # Return top 3 most relevant

        except Exception as e:
            _logger.error(f"Error extracting artefacts: {e}")
            # If error occurs, return the latest artefact from notes as fallback
            if notes_with_artefacts:
                _logger.info(
                    "Error occurred, returning latest artefact from notes as fallback"
                )
                latest_note = max(
                    notes_with_artefacts,
                    key=lambda n: getattr(n, "timestamp", 0),
                    default=None,
                )
                if latest_note and latest_note.artefact_id:
                    return [latest_note.artefact_id]
            return []

    def get_artefacts_by_ids(self, artefact_ids: List[str]) -> List[Artefact]:
        """
        Retrieve artefact objects by their IDs.

        Args:
            artefact_ids: List of artefact IDs to retrieve

        Returns:
            List of Artefact objects
        """
        artefacts = []
        for artefact_id in artefact_ids:
            try:
                artefact = self._storage.retrieve_from_id(artefact_id)
                artefacts.append(artefact)
            except (ValueError, AttributeError) as e:
                _logger.warning(f"Could not retrieve artefact {artefact_id}: {e}")
                continue
        return artefacts
