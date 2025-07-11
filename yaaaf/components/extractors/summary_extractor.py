from typing import List, Optional

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.extractors.base_extractor import BaseExtractor
from yaaaf.components.extractors.prompts import summary_extractor_prompt


class SummaryExtractor(BaseExtractor):
    """
    SummaryExtractor is a class that generates a summary artifact from conversation notes.
    It creates a comprehensive summary with main findings, reasoning, and references.
    """

    _summary_extractor_prompt = summary_extractor_prompt

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client
        self._storage = ArtefactStorage()

    async def extract(self, notes: Optional[List[Note]] = None) -> str:
        """
        Extract a summary from the conversation notes and create an artifact.

        Args:
            notes: List of conversation notes to summarize

        Returns:
            String containing the artifact reference and summary message
        """
        if not notes:
            return ""

        # Extract conversation content from notes
        conversation_content = []
        all_artifacts = []

        for note in notes:
            if not note.internal and note.message:
                conversation_content.append(f"**{note.agent_name}**: {note.message}")

                # Collect artifacts from this note
                if note.artefact_id:
                    try:
                        artifact = self._storage.retrieve_from_id(note.artefact_id)
                        if artifact:
                            all_artifacts.append(artifact)
                    except ValueError:
                        pass  # Artifact not found, continue

        if not conversation_content:
            return ""

        # Generate summary using the client
        summary_messages = Messages().add_system_prompt(
            self._summary_extractor_prompt.complete(
                conversation_content="\n".join(conversation_content)
            )
        )
        summary_messages = summary_messages.add_user_utterance(
            "Create the summary following the specified format."
        )
        response = await self._client.predict(summary_messages)
        summary_content = response.message

        # Create and store summary artifact
        summary_artifact = Artefact(
            type="summary",
            description="Conversation summary with main findings, reasoning, and references",
            summary=summary_content,
            id=create_hash(summary_content),
        )

        self._storage.store_artefact(summary_artifact.id, summary_artifact)

        return f"The summary of this conversation is in this artefact: <artefact type='summary'>{summary_artifact.id}</artefact>"
