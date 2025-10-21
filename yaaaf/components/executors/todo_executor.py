import logging
import pandas as pd
from io import StringIO
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class TodoExecutor(ToolExecutor):
    """Executor for todo list management and task tracking."""

    def __init__(self, agents_and_sources_and_tools_list: str = ""):
        """Initialize todo executor."""
        self._storage = ArtefactStorage()
        self._agents_and_sources_and_tools_list = agents_and_sources_and_tools_list
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for todo management."""
        return {
            "messages": messages,
            "notes": notes or [],
            "agents_list": self._agents_and_sources_and_tools_list
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract table specification from response."""
        return get_first_text_between_tags(response, "```table", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Create or update todo list table."""
        try:
            # Parse the table instruction and create DataFrame
            if instruction.strip():
                # Try to parse as CSV
                try:
                    df = pd.read_csv(StringIO(instruction))
                except Exception:
                    # If CSV parsing fails, create a simple todo structure
                    df = self._create_todo_table(instruction, context)
            else:
                # Create empty todo template
                df = self._create_empty_todo_table()
                
            return df, None
            
        except Exception as e:
            error_msg = f"Error processing todo list: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def _create_todo_table(self, instruction: str, context: Dict[str, Any]) -> pd.DataFrame:
        """Create a todo table from instruction text."""
        # Split instruction into lines and create todo items
        lines = [line.strip() for line in instruction.split('\n') if line.strip()]
        
        todo_items = []
        for i, line in enumerate(lines, 1):
            # Remove common prefixes like numbers, bullets, etc.
            clean_line = line.lstrip('0123456789.- *•')
            todo_items.append({
                "ID": i,
                "Task": clean_line,
                "Status": "Pending",
                "Priority": "Medium",
                "Agent": "TBD"
            })
        
        return pd.DataFrame(todo_items)

    def _create_empty_todo_table(self) -> pd.DataFrame:
        """Create an empty todo table template."""
        return pd.DataFrame(columns=["ID", "Task", "Status", "Priority", "Agent"])

    def validate_result(self, result: Any) -> bool:
        """Validate todo list result."""
        return result is not None and isinstance(result, pd.DataFrame)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform todo list to artifact."""
        # Convert DataFrame to CSV string for storage
        csv_content = result.to_csv(index=False)
        
        return Artefact(
            artifact_id=artifact_id,
            artifact_type="table",
            content=csv_content,
            name=f"todo_list_{create_hash(instruction)[:8]}",
            description=f"Todo list with {len(result)} tasks"
        )