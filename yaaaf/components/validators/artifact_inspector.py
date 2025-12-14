"""Utilities for inspecting artifacts for validation."""

import logging
from typing import Optional

import pandas as pd

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage

_logger = logging.getLogger(__name__)

# Maximum tokens for text inspection (roughly 4 chars per token)
MAX_TEXT_TOKENS = 1000
MAX_TEXT_CHARS = MAX_TEXT_TOKENS * 4

# Maximum rows for table inspection
MAX_TABLE_ROWS = 20


def inspect_artifact(artifact: Artefact) -> str:
    """Inspect an artifact and return a string representation for validation.

    Args:
        artifact: The artifact to inspect

    Returns:
        String representation suitable for LLM validation
    """
    if artifact is None:
        return "No artifact provided"

    artifact_type = artifact.type.lower() if artifact.type else "unknown"

    if artifact_type == Artefact.Types.TABLE:
        return inspect_table(artifact)
    elif artifact_type == Artefact.Types.TEXT:
        return inspect_text(artifact)
    elif artifact_type == Artefact.Types.IMAGE:
        return inspect_image(artifact)
    elif artifact_type == Artefact.Types.MODEL:
        return inspect_model(artifact)
    else:
        return f"Artifact of type '{artifact_type}' (inspection not supported)"


def inspect_table(artifact: Artefact) -> str:
    """Inspect a table artifact.

    Returns schema and first 20 rows as markdown.

    Args:
        artifact: Table artifact with DataFrame in data field

    Returns:
        Markdown representation of schema + sample rows
    """
    if artifact.data is None:
        return "Table artifact has no data"

    df = artifact.data
    if not isinstance(df, pd.DataFrame):
        return f"Table artifact data is not a DataFrame: {type(df)}"

    parts = []

    # Schema information
    parts.append("**Schema:**")
    parts.append(f"- Rows: {len(df)}")
    parts.append(f"- Columns: {len(df.columns)}")
    parts.append("")
    parts.append("| Column | Type |")
    parts.append("|--------|------|")
    for col in df.columns:
        dtype = str(df[col].dtype)
        parts.append(f"| {col} | {dtype} |")

    parts.append("")

    # Sample rows
    sample_df = df.head(MAX_TABLE_ROWS)
    parts.append(f"**First {len(sample_df)} rows:**")
    parts.append("")

    try:
        # Convert to markdown table
        markdown_table = sample_df.to_markdown(index=False)
        parts.append(markdown_table)
    except Exception as e:
        _logger.warning(f"Failed to convert DataFrame to markdown: {e}")
        parts.append(str(sample_df))

    return "\n".join(parts)


def inspect_text(artifact: Artefact) -> str:
    """Inspect a text artifact.

    Returns first 1000 tokens (approximately 4000 characters).

    Args:
        artifact: Text artifact

    Returns:
        Truncated text content
    """
    # Try to get text from various fields
    text = None

    if artifact.code:
        text = artifact.code
    elif artifact.summary:
        text = artifact.summary
    elif artifact.description:
        text = artifact.description

    if text is None:
        return "Text artifact has no content"

    # Truncate to max characters
    if len(text) > MAX_TEXT_CHARS:
        truncated = text[:MAX_TEXT_CHARS]
        return f"{truncated}\n\n[... truncated, {len(text)} total characters ...]"

    return text


def inspect_image(artifact: Artefact) -> str:
    """Inspect an image artifact.

    Returns metadata about the image (cannot show actual image to LLM).

    Args:
        artifact: Image artifact

    Returns:
        Description of the image artifact
    """
    parts = ["**Image Artifact:**"]

    if artifact.description:
        parts.append(f"- Description: {artifact.description}")

    if artifact.image:
        parts.append(f"- Path: {artifact.image}")

    if artifact.code:
        # Code used to generate the image
        code_preview = artifact.code[:500] if len(artifact.code) > 500 else artifact.code
        parts.append(f"- Generation code preview:\n```python\n{code_preview}\n```")

    return "\n".join(parts)


def inspect_model(artifact: Artefact) -> str:
    """Inspect a model artifact.

    Returns metadata about the trained model.

    Args:
        artifact: Model artifact

    Returns:
        Description of the model
    """
    parts = ["**Model Artifact:**"]

    if artifact.description:
        parts.append(f"- Description: {artifact.description}")

    if artifact.model:
        model_type = type(artifact.model).__name__
        parts.append(f"- Model type: {model_type}")

        # Try to get model parameters
        try:
            if hasattr(artifact.model, "get_params"):
                params = artifact.model.get_params()
                parts.append(f"- Parameters: {params}")
        except Exception:
            pass

    return "\n".join(parts)


def inspect_artifact_from_result(
    result_string: str, storage: Optional[ArtefactStorage] = None
) -> str:
    """Extract and inspect artifact from an agent result string.

    Args:
        result_string: Agent result containing artifact references
        storage: Optional artifact storage (uses singleton if not provided)

    Returns:
        Inspection of the first artifact found, or error message
    """
    import re

    if storage is None:
        storage = ArtefactStorage()

    # Find artifact reference
    match = re.search(r"<artefact[^>]*>([^<]+)</artefact>", result_string)
    if not match:
        return "No artifact found in result"

    artifact_id = match.group(1)

    try:
        artifact = storage.retrieve_from_id(artifact_id)
        return inspect_artifact(artifact)
    except Exception as e:
        _logger.warning(f"Failed to retrieve artifact {artifact_id}: {e}")
        return f"Failed to retrieve artifact: {e}"
