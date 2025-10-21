import logging
import pandas as pd
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.extractors.artefact_extractor import ArtefactExtractor

_logger = logging.getLogger(__name__)


class ArtifactProcessorExecutor(ToolExecutor):
    """Executor for processing artifacts and creating table outputs."""

    def __init__(self, client, output_tag: str = "```table"):
        """Initialize artifact processor executor."""
        self._storage = ArtefactStorage()
        self._artefact_extractor = ArtefactExtractor(client)
        self._output_tag = output_tag
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for artifact processing."""
        # Get artifacts from the last utterance
        last_utterance = messages.utterances[-1] if messages.utterances else None
        artefact_list = []
        
        if last_utterance:
            artefact_list = get_artefacts_from_utterance_content(last_utterance.content)
        
        return {
            "messages": messages,
            "notes": notes or [],
            "artifacts": artefact_list,
            "last_utterance": last_utterance
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract table specification from response."""
        tag = self._output_tag.replace('```', '').replace('`', '')
        return get_first_text_between_tags(response, f"```{tag}", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Process artifacts and create table output."""
        try:
            artifacts = context.get("artifacts", [])
            
            if not artifacts:
                return None, "No artifacts found to process"
            
            # Create a simple DataFrame with artifact information
            artifact_data = []
            for i, artifact in enumerate(artifacts):
                artifact_data.append({
                    "Index": i + 1,
                    "Type": artifact.type,
                    "Name": getattr(artifact, 'name', artifact.id),
                    "Description": getattr(artifact, 'description', 'No description'),
                    "ID": artifact.id
                })
            
            df = pd.DataFrame(artifact_data)
            
            # If instruction contains specific processing logic, apply it here
            # For now, return the basic artifact summary table
            
            return df, None
            
        except Exception as e:
            error_msg = f"Error processing artifacts: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def validate_result(self, result: Any) -> bool:
        """Validate artifact processing result."""
        return result is not None and isinstance(result, pd.DataFrame)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform processed result to artifact."""
        # Convert DataFrame to CSV string for storage
        csv_content = result.to_csv(index=False)
        
        return Artefact(
            artifact_id=artifact_id,
            artifact_type="table",
            content=csv_content,
            name=f"processed_table_{create_hash(instruction)[:8]}",
            description=f"Processed artifact table: {len(result)} items"
        )