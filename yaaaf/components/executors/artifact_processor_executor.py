import logging
import mdpd
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
        
    def _parse_markdown_table(self, text: str) -> pd.DataFrame | None:
        """Parse markdown table from text into DataFrame using mdpd library."""
        if not text:
            return None
            
        try:
            # Use mdpd to parse the markdown table directly
            df = mdpd.from_md(text)
            _logger.info(f"Parsed markdown table with {len(df)} rows and {len(df.columns)} columns")
            return df
            
        except Exception as e:
            _logger.warning(f"Failed to parse markdown table with mdpd: {e}")
            return None
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for artifact processing."""
        # Use the common artifact extraction method from base class
        artefact_list = self.extract_artifacts_from_messages(messages, notes)
        last_utterance = messages.utterances[-1] if messages.utterances else None
        
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
            # Create a simple DataFrame with the table in the instructions
            df = self._parse_markdown_table(instruction)

            # If no markdown table found in instruction, create DataFrame from artifacts
            if df is None:
                return "No valid markdown table found in instruction", None
            
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
        return Artefact(
            id=artifact_id,
            type=Artefact.Types.TABLE,
            data=result,
            description=f"Processed artifact table: {len(result)} items"
        )