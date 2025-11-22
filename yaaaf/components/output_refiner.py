"""OutputRefiner - Formats final artifacts for user-friendly display on the frontend."""

import logging
import re
from typing import Optional

import pandas as pd

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage

_logger = logging.getLogger(__name__)


class OutputRefiner:
    """Formats final artifacts for user-friendly display on the frontend.

    Takes artifacts and converts them to markdown format suitable for display:
    - Tables: Converted to markdown tables (limited to 20 rows)
    - Images: Converted to markdown image syntax
    - Text: Not refined (displayed as-is)
    """

    def __init__(self, storage: ArtefactStorage):
        """Initialize the OutputRefiner with artifact storage.

        Args:
            storage: The ArtefactStorage instance to retrieve artifacts from
        """
        self.storage = storage

    def format_artifact(self, artifact_id: str) -> Optional[str]:
        """Format an artifact based on its type.

        Args:
            artifact_id: The ID of the artifact to format

        Returns:
            Markdown-formatted string for display, or None if not applicable
        """
        try:
            artifact = self.storage.retrieve_from_id(artifact_id)

            if artifact.type == Artefact.Types.TABLE:
                return self._format_table(artifact)
            elif artifact.type == Artefact.Types.IMAGE:
                return self._format_image(artifact_id, artifact)
            elif artifact.type == Artefact.Types.TEXT:
                # Text artifacts don't need refinement
                return None
            else:
                # Other types (model, plan, etc.) don't need refinement
                return None

        except Exception as e:
            _logger.error(f"Error formatting artifact {artifact_id}: {e}")
            return None

    def _format_table(self, artifact: Artefact) -> Optional[str]:
        """Convert table artifact to markdown table (max 20 rows).

        Args:
            artifact: The artifact containing table data

        Returns:
            Markdown table string, or None if no data
        """
        if artifact.data is None:
            _logger.warning("Table artifact has no data")
            return None

        try:
            df = artifact.data

            if not isinstance(df, pd.DataFrame):
                _logger.warning(f"Table artifact data is not a DataFrame: {type(df)}")
                return None

            if df.empty:
                return "*(Empty table)*"

            # Limit to first 20 rows
            total_rows = len(df)
            df_display = df.head(20)

            # Convert to markdown
            markdown_table = df_display.to_markdown(index=False)

            # Add row count information if table was truncated
            if total_rows > 20:
                markdown_table += f"\n\n*Showing 20 of {total_rows} rows*"

            return markdown_table

        except Exception as e:
            _logger.error(f"Error converting table to markdown: {e}")
            return None

    def _format_image(self, artifact_id: str, artifact: Artefact) -> Optional[str]:
        """Return markdown image syntax for artifact.

        Args:
            artifact_id: The ID of the artifact
            artifact: The artifact containing image data

        Returns:
            Markdown image string
        """
        if artifact.image is None:
            _logger.warning("Image artifact has no image data")
            return None

        try:
            # Create markdown image with data URI
            # The image is stored as base64, so we can embed it directly
            return f"![Visualization](data:image/png;base64,{artifact.image})"

        except Exception as e:
            _logger.error(f"Error formatting image: {e}")
            return None


def extract_artifact_id(completion_message: str) -> Optional[str]:
    """Extract artifact ID from a completion message.

    Args:
        completion_message: Message like "Operation completed. Result: <artefact type='table'>abc123</artefact> <taskcompleted/>"

    Returns:
        The artifact ID, or None if not found
    """
    # Match pattern: <artefact type='...'>{id}</artefact>
    match = re.search(r'<artefact[^>]*>([^<]+)</artefact>', completion_message)
    if match:
        return match.group(1)
    return None
