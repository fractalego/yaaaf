import logging
import mdpd
from typing import List, Optional

import pandas as pd

from yaaaf.components.agents.artefact_utils import (
    get_table_and_model_from_artefacts,
    get_artefacts_from_utterance_content,
)
from yaaaf.components.extractors.artefact_extractor import ArtefactExtractor
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.prompts import numerical_sequences_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.texts import no_artefact_text
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class NumericalSequencesAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```table"
    _stop_sequences = _completing_tags
    _max_steps = 1
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client
        self._artefact_extractor = ArtefactExtractor(client)

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        thinking_artifacts = []  # Track all thinking artifacts
        last_utterance = messages.utterances[-1]
        artefact_list: List[Artefact] = get_artefacts_from_utterance_content(
            last_utterance.content
        )
        # Try to extract artefacts from notes if none found in utterance
        artefact_list = await self._try_extract_artefacts_from_notes(
            artefact_list, last_utterance, notes
        )

        if not artefact_list:
            return no_artefact_text

        df, _ = get_table_and_model_from_artefacts(artefact_list)
        messages = messages.add_system_prompt(
            numerical_sequences_agent_prompt_template.complete(
                table=df.to_markdown(index=False),
            )
        )
        output_df: pd.DataFrame = pd.DataFrame()
        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

            

            # Process response to create thinking artifacts

            clean_message, thinking_artifact_ref = self._process_client_response(response, notes)

            
            if thinking_artifact_ref:
                thinking_artifacts.append(thinking_artifact_ref)
            answer = clean_message

            if (
                notes is not None and step_idx > 0
            ):  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Numerical Sequences Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            messages.add_assistant_utterance(answer)
            output = get_first_text_between_tags(answer, self._output_tag, "```")
            if output.strip() != "":
                try:
                    output_df = mdpd.from_md(output)
                except Exception as e:
                    _logger.warning(f"Failed to parse markdown table: {e}")
                    continue

            if self.is_complete(answer) or answer.strip() == "":
                break

            messages.add_assistant_utterance(
                f"The result is <result>{output}</result>. If the initial query {last_utterance} is answered write {self._completing_tags[0]} at the beginning of your answer.\n"
                f"If there are errors try to correct them in the next steps.\n"
            )

        if output_df.empty:
            return "Could not extract numerical data from the provided artefacts. Please try again with content that contains quantitative information."

        hash_id: str = str(hash(str(messages))).replace("-", "")
        self._storage.store_artefact(
            hash_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description=f"Numerical sequences extracted from search results: {str(messages)}",
                data=output_df,
                id=hash_id,
            ),
        )
        # Prepare the final response with thinking artifacts at the beginning

        final_response = ""

        if thinking_artifacts:

            final_response = " ".join(thinking_artifacts) + " "

        final_response += f"Numerical data has been extracted and structured into a table <artefact type='numerical-sequences-table'>{hash_id}</artefact>."

        

        return final_response

    @staticmethod
    def get_info() -> str:
        return "This agent analyzes search results or text content and extracts numerical data into structured tables suitable for visualization."

    def get_description(self) -> str:
        return f"""
Numerical Sequences agent: {self.get_info()}
To call this agent write {self.get_opening_tag()} ENGLISH QUERY DESCRIBING WHAT NUMERICAL DATA TO EXTRACT and <artefact> SEARCH RESULT ARTEFACT </artefact> {self.get_closing_tag()}
This agent acts as an intermediary between search agents and visualization agents.
The arguments within the tags must be: 
1) instructions about what numerical patterns or data to extract (e.g., "extract yearly sales data", "find population trends by country")
2) the artefacts <artefact type="search-result"> ... </artefact> that contain the raw data from search agents.
Both arguments are required.
This agent specializes in identifying and structuring:
- Time series data (dates, years, months with values)
- Statistical comparisons (counts, percentages, ratios)
- Categorical numerical data (data organized by groups or categories)
- Trends and patterns suitable for charts and graphs
Do *not* use images in the arguments of this agent.
        """
