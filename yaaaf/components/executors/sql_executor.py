import logging
from typing import Any, Tuple, Optional, Dict, List

import pandas as pd

from yaaaf.components.agents.artefacts import Artefact
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.sources.sqlite_source import SqliteSource

from .base import ToolExecutor

_logger = logging.getLogger(__name__)


class SQLExecutor(ToolExecutor):
    """Executor for SQL queries against database sources."""

    def __init__(self, sources: List[SqliteSource]):
        """Initialize with database sources.

        Args:
            sources: List of SqliteSource objects to query against
        """
        self._sources = sources

    async def prepare_context(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> Dict[str, Any]:
        """Prepare context by loading database schemas.

        Returns:
            Dictionary containing schemas for all data sources
        """
        schemas = {}
        for source in self._sources:
            # Get schema description for each source
            schema = source.get_description()
            if schema:
                schemas[source.filename] = schema

        return {"schemas": schemas}

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract SQL query from response.

        Looks for SQL queries between ```sql tags.

        Args:
            response: The agent's response

        Returns:
            The SQL query or None
        """
        return get_first_text_between_tags(response, "sql", "sql")

    async def execute_operation(
        self, instruction: str, context: Dict[str, Any]
    ) -> Tuple[Any, Optional[str]]:
        """Execute SQL query against data sources.

        Tries each data source until one succeeds.

        Args:
            instruction: The SQL query to execute
            context: The prepared context (not used for SQL)

        Returns:
            Tuple of (DataFrame result, error message)
        """
        for source in self._sources:
            try:
                result_df = self._execute_query_on_source(source, instruction)
                if result_df is not None and not self._is_error_dataframe(result_df):
                    return result_df, None
            except Exception as e:
                _logger.error(f"Error executing query on {source.filename}: {str(e)}")
                continue

        # No source could execute the query
        return None, "Failed to execute query on any data source"

    def validate_result(self, result: Any) -> bool:
        """Validate SQL query result.

        Args:
            result: The result DataFrame

        Returns:
            True if valid DataFrame, False otherwise
        """
        if result is None:
            return False

        if not isinstance(result, pd.DataFrame):
            return False

        # Check if it's an error DataFrame
        if self._is_error_dataframe(result):
            return False

        return True

    def transform_to_artifact(
        self, result: Any, instruction: str, artifact_id: str
    ) -> Artefact:
        """Transform DataFrame result to table artifact.

        Args:
            result: The DataFrame result
            instruction: The SQL query
            artifact_id: The ID for the artifact

        Returns:
            A table Artefact
        """
        return Artefact(
            type=Artefact.Types.TABLE,
            description="SQL query result",
            code=instruction,  # Store the SQL query
            data=result,  # Store the DataFrame
            id=artifact_id,
        )

    def _execute_query_on_source(
        self, source: SqliteSource, query: str
    ) -> Optional[pd.DataFrame]:
        """Execute query on a single source.

        Args:
            source: The data source
            query: The SQL query

        Returns:
            DataFrame or None
        """
        try:
            return source.read_query(query)
        except Exception as e:
            _logger.error(f"Error executing on {source.filename}: {e}")
            return None

    def _is_error_dataframe(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame represents an error.

        Args:
            df: The DataFrame to check

        Returns:
            True if error DataFrame
        """
        # Check for specific error DataFrame format
        if len(df.columns) == 1 and "error" in df.columns[0].lower():
            return True

        # Check if all values are error-like strings
        if df.shape == (1, 1) and isinstance(df.iloc[0, 0], str):
            error_str = df.iloc[0, 0].lower()
            if any(word in error_str for word in ["error", "failed", "exception"]):
                return True

        return False

    def get_feedback_message(self, error: str) -> str:
        """Generate SQL-specific error feedback.

        Args:
            error: The error message

        Returns:
            Formatted feedback
        """
        return f"SQL Error: {error}. Please check your query syntax and try again."
