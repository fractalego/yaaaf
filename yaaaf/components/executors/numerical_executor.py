import logging
import pandas as pd
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefact_utils import (
    get_table_and_model_from_artefacts,
    get_artefacts_from_utterance_content,
)
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class NumericalExecutor(ToolExecutor):
    """Executor for numerical sequence analysis and processing."""

    def __init__(self):
        """Initialize numerical executor."""
        self._storage = ArtefactStorage()

    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for numerical analysis."""
        # Extract artifacts from messages using the base executor's method
        artefact_list = []

        # Check messages for artifacts
        if messages.utterances:
            for utterance in reversed(messages.utterances):
                artefacts = get_artefacts_from_utterance_content(utterance.content)
                if artefacts:
                    artefact_list = artefacts
                    break

        # Also check notes if provided
        if not artefact_list and notes:
            for note in reversed(notes):
                if note.message:
                    artefacts = get_artefacts_from_utterance_content(note.message)
                    if artefacts:
                        artefact_list = artefacts
                        break

        # Extract table data and model from artifacts
        table_data, model_info = get_table_and_model_from_artefacts(artefact_list)
        
        return {
            "messages": messages,
            "notes": notes or [],
            "table_data": table_data,
            "model_info": model_info
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract table specification from response."""
        return get_first_text_between_tags(response, "```table", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Process numerical sequences and create table."""
        try:
            table_data = context.get("table_data")
            
            if table_data is None:
                # Create a simple numerical sequence table based on instruction
                # This is a simplified implementation - real logic would be more complex
                return self._create_sequence_table(instruction), None
            else:
                # Process existing table data for numerical analysis
                return self._analyze_numerical_data(table_data, instruction), None
                
        except Exception as e:
            error_msg = f"Error processing numerical data: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def _create_sequence_table(self, instruction: str) -> pd.DataFrame:
        """Create a numerical sequence table based on instruction."""
        # Simple implementation - generates basic sequences
        # Real implementation would parse instruction and create appropriate sequences
        df = pd.DataFrame({
            "Index": range(1, 11),
            "Value": [i**2 for i in range(1, 11)],  # Simple square sequence
            "Description": [f"Value at position {i}" for i in range(1, 11)]
        })
        return df

    def _analyze_numerical_data(self, table_data: pd.DataFrame, instruction: str) -> pd.DataFrame:
        """Analyze existing numerical data."""
        # Simple analysis - add basic statistics
        numeric_cols = table_data.select_dtypes(include=['number']).columns
        
        if len(numeric_cols) > 0:
            analysis_data = []
            for col in numeric_cols:
                analysis_data.append({
                    "Column": col,
                    "Mean": table_data[col].mean(),
                    "Std": table_data[col].std(),
                    "Min": table_data[col].min(),
                    "Max": table_data[col].max()
                })
            return pd.DataFrame(analysis_data)
        else:
            return table_data

    def validate_result(self, result: Any) -> bool:
        """Validate numerical processing result."""
        return result is not None and isinstance(result, pd.DataFrame)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform numerical analysis to artifact."""
        # Convert DataFrame to CSV string for storage
        csv_content = result.to_csv(index=False)
        
        return Artefact(
            id=artifact_id,
            type=Artefact.Types.TABLE,
            data=result,
            description=f"Numerical sequence analysis: {instruction[:50]}..."
        )