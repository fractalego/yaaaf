"""
Response processing utilities for the orchestrator.
Handles response cleaning, artifact management, and note creation.
"""
import logging
from typing import List, Optional, TYPE_CHECKING

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.agents.artefacts import Artefact

if TYPE_CHECKING:
    from yaaaf.components.data_types import Note, ClientResponse

_logger = logging.getLogger(__name__)


class ResponseProcessor:
    """Processes orchestrator and agent responses."""
    
    @staticmethod
    def create_orchestrator_note(
        response: str, 
        agent_name: str, 
        model_name: Optional[str], 
        notes: Optional[List["Note"]]
    ) -> None:
        """Create and add a note for orchestrator response."""
        if notes is None:
            return
        
        from yaaaf.components.data_types import Note
        
        artefacts = get_artefacts_from_utterance_content(response)
        
        note = Note(
            message=Note.clean_agent_tags(response),
            artefact_id=artefacts[0].id if artefacts else None,
            agent_name=agent_name,
            model_name=model_name,
        )
        note.internal = False
        notes.append(note)
    
    @staticmethod
    def create_agent_note(
        response: str,
        agent_name: str,
        agent_model_name: Optional[str],
        notes: Optional[List["Note"]]
    ) -> None:
        """Create and add a note for agent response."""
        if notes is None:
            return
        
        from yaaaf.components.data_types import Note
        
        artefacts = get_artefacts_from_utterance_content(response)
        extracted_agent_name = Note.extract_agent_name_from_tags(response)
        final_agent_name = extracted_agent_name or agent_name
        
        note = Note(
            message=Note.clean_agent_tags(response),
            artefact_id=artefacts[0].id if artefacts else None,
            agent_name=final_agent_name,
            model_name=agent_model_name,
        )
        note.internal = False
        notes.append(note)
    
    @staticmethod
    def process_client_response(
        response: "ClientResponse", 
        notes: Optional[List["Note"]], 
        agent_name: str
    ) -> tuple[str, Optional[str]]:
        """Process client response and create thinking artifacts."""
        from yaaaf.components.agents.artefacts import ArtefactStorage
        from yaaaf.components.agents.hash_utils import create_hash
        from yaaaf.components.data_types import Note
        
        thinking_artifact_ref = None
        
        # Create thinking artifact if present
        if response.thinking_content:
            thinking_id = create_hash(
                f"thinking_{agent_name}_{response.thinking_content}"
            )
            
            storage = ArtefactStorage()
            storage.store_artefact(
                thinking_id,
                Artefact(
                    type=Artefact.Types.THINKING,
                    description=f"Thinking process from {agent_name}",
                    code=response.thinking_content,
                    id=thinking_id,
                ),
            )
            
            if notes is not None:
                note = Note(
                    message=f"[Thinking] Created thinking artifact: {thinking_id}",
                    artefact_id=thinking_id,
                    agent_name=agent_name,
                    model_name=None,
                    internal=True,
                )
                notes.append(note)
            
            thinking_artifact_ref = f"<artefact type='thinking'>{thinking_id}</artefact>"
        
        return response.message, thinking_artifact_ref
    
    @staticmethod
    def handle_todo_artifact(
        response: str,
        agent_name: str,
        artefacts: List[Artefact]
    ) -> Optional[str]:
        """Check if response contains todo artifact and return its ID."""
        _logger.info(f"[RESPONSE_PROCESSOR] Checking for todo artifact - agent: {agent_name}, artifacts: {len(artefacts)}")
        if agent_name == "todoagent" and artefacts:
            for artifact in artefacts:
                _logger.info(f"[RESPONSE_PROCESSOR] Found artifact type: {artifact.type}, id: {artifact.id}")
                if artifact.type == Artefact.Types.TODO_LIST:
                    _logger.info(f"[RESPONSE_PROCESSOR] Found todo artifact with ID: {artifact.id}")
                    return artifact.id
        return None
    
    @staticmethod
    def make_output_visible(response: str) -> str:
        """Make artifacts visible by adding display markers."""
        # Handle images
        if "<artefact type='image'>" in response:
            image_artefact = get_artefacts_from_utterance_content(response)[0]
            response = f"<imageoutput>{image_artefact.id}</imageoutput>\n{response}"
        
        # Handle tables
        artefacts = get_artefacts_from_utterance_content(response)
        for artefact in artefacts:
            if artefact.data is not None and hasattr(artefact.data, "to_markdown"):
                try:
                    from yaaaf.components.orchestrator.table_formatter import TableFormatter
                    
                    if artefact.type == Artefact.Types.TODO_LIST:
                        markdown_table = TableFormatter.sanitize_dataframe_for_markdown(artefact.data)
                        logger_msg = f"Added full todo-list table with {len(artefact.data)} rows to output"
                    else:
                        markdown_table = TableFormatter.sanitize_and_truncate_dataframe_for_markdown(artefact.data)
                        logger_msg = f"Added table with {len(artefact.data)} rows to output"
                    
                    response = f"<markdown>{markdown_table}</markdown>\n{response}"
                    _logger.info(logger_msg)
                except Exception as e:
                    _logger.warning(f"Failed to process table for display: {e}")
        
        return response