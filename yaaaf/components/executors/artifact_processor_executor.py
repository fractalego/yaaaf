import logging
import re
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
            df = mdpd.from_md(text)
            _logger.info(f"Parsed markdown table with {len(df)} rows and {len(df.columns)} columns")
            return df
        except Exception as e:
            _logger.warning(f"Failed to parse markdown table with mdpd: {e}. Trying fallback parser.")
            _logger.debug(f"Table content that failed parsing:\n{text}")
            return self._parse_markdown_table_fallback(text)

    def _parse_markdown_table_fallback(self, text: str) -> pd.DataFrame | None:
        """Lenient fallback parser that normalizes mismatched column counts."""
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        # Keep only pipe-delimited lines, skip separator rows (|---|---|)
        data_lines = [
            line for line in lines
            if line.startswith("|") and not re.match(r"^\|[-\s|:]+\|$", line)
        ]
        if len(data_lines) < 2:
            _logger.warning("Fallback parser: not enough data rows in table")
            return None

        def parse_row(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip("|").split("|")]

        headers = parse_row(data_lines[0])
        n_cols = len(headers)
        rows = []
        for line in data_lines[1:]:
            row = parse_row(line)
            if len(row) < n_cols:
                row.extend([""] * (n_cols - len(row)))
            elif len(row) > n_cols:
                # Join overflow cells into the last column
                row = row[: n_cols - 1] + [" ".join(row[n_cols - 1 :])]
            rows.append(row)

        df = pd.DataFrame(rows, columns=headers)
        _logger.info(f"Fallback parser: parsed table with {len(df)} rows and {n_cols} columns")
        return df
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for artifact processing."""
        context = await super().prepare_context(messages, notes)
        context["last_utterance"] = messages.utterances[-1] if messages.utterances else None
        return context

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract table specification from response."""
        tag = self._output_tag.replace('```', '').replace('`', '')
        instruction = get_first_text_between_tags(response, f"```{tag}", "```")
        if instruction is None:
            _logger.warning(
                f"AnswererAgent: no ```{tag} block found in LLM response. "
                f"Full response:\n{response}"
            )
        else:
            _logger.info(f"AnswererAgent: extracted table instruction ({len(instruction)} chars)")
        return instruction

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
            
            _logger.info(f"Answerer output:\n{df.to_markdown(index=False)}")
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