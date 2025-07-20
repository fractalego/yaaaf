import mdpd
import re
import pandas as pd
import logging
from typing import Optional, List

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.extractors.artefact_extractor import ArtefactExtractor
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.agents.prompts import answerer_agent_prompt_template
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class AnswererAgent(BaseAgent):
    _system_prompt = answerer_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```table"
    _stop_sequences = [task_completed_tag]
    _max_steps = 3
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client
        self._artefact_extractor = ArtefactExtractor(client)
        self.set_budget(1)

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        last_utterance = messages.utterances[-1]
        artefact_list: List[Artefact] = get_artefacts_from_utterance_content(
            last_utterance.content
        )
        
        # Try to extract artefacts from notes if none found in utterance
        artefact_list = await self._try_extract_artefacts_from_notes(
            artefact_list, last_utterance, notes
        )

        if not artefact_list:
            return "No artifacts found to analyze. Please provide artifacts from document retrieval, SQL queries, web search, or other agents."

        # Process artifacts and create content for prompt
        artifacts_content = self._process_artifacts(artefact_list)
        
        # Add system prompt with artifacts content
        messages = messages.add_system_prompt(
            self._system_prompt.complete(artifacts_content=artifacts_content)
        )

        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            answer = response.message

            # Log internal thinking step
            if notes is not None and step_idx > 0:
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Answerer Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            if self.is_complete(answer) or answer.strip() == "":
                break

            matches = re.findall(
                rf"{self._output_tag}(.+?)```",
                answer,
                re.DOTALL | re.MULTILINE,
            )

            if matches:
                try:
                    # Parse the markdown table
                    df = mdpd.from_md(matches[0])
                    
                    # Validate table structure
                    if not self._validate_output_table(df):
                        messages = messages.add_user_utterance(
                            f"The table format is incorrect. Please provide a table with exactly these columns: | paragraph | source |\n"
                            f"Current columns: {list(df.columns)}\n"
                            f"Try again with the correct format."
                        )
                        continue

                    # Store the answer as an artifact
                    answer_id: str = str(hash(str(messages))).replace("-", "")
                    self._storage.store_artefact(
                        answer_id,
                        Artefact(
                            type=Artefact.Types.TABLE,
                            description=f"Research answer based on {len(artefact_list)} artifacts",
                            data=df,
                            id=answer_id,
                        ),
                    )
                    
                    return f"Analysis complete. The research answer is in this artifact: <artefact type='table'>{answer_id}</artefact>"
                    
                except Exception as e:
                    _logger.warning(f"Failed to parse table output: {e}")
                    messages = messages.add_user_utterance(
                        f"Failed to parse the table. Error: {e}\n"
                        f"Please ensure the table is in valid markdown format with | paragraph | source | columns."
                    )
                    continue
            else:
                messages = messages.add_user_utterance(
                    f"No table found in the response. Please provide your answer as a markdown table between ```table ... ``` tags.\n"
                    f"The table must have these columns: | paragraph | source |"
                )

        return "Failed to generate a proper research answer after maximum attempts."

    def _process_artifacts(self, artefact_list: List[Artefact]) -> str:
        """Process multiple artifacts into a formatted string for the prompt."""
        artifacts_content = []
        
        for i, artifact in enumerate(artefact_list, 1):
            content_section = f"\n--- Artifact {i} ---\n"
            content_section += f"Type: {artifact.type}\n"
            content_section += f"Description: {artifact.description}\n"
            
            if artifact.type == Artefact.Types.TABLE and artifact.data is not None:
                content_section += "Data (Markdown Table):\n"
                content_section += artifact.data.to_markdown(index=False)
            elif artifact.code:
                content_section += f"Code:\n{artifact.code}\n"
            elif artifact.summary:
                content_section += f"Summary:\n{artifact.summary}\n"
            else:
                content_section += "Content: [No readable content available]\n"
            
            artifacts_content.append(content_section)
        
        return "\n".join(artifacts_content)

    def _validate_output_table(self, df: pd.DataFrame) -> bool:
        """Validate that the output table has the correct structure."""
        expected_columns = ["paragraph", "source"]
        return (
            len(df.columns) == 2 and
            all(col.lower().strip() in expected_columns for col in df.columns)
        )

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return (
            "This agent synthesizes information from multiple artifacts to generate comprehensive research answers"
        )

    def get_description(self) -> str:
        return f"""
Answerer agent: {self.get_info()}.
This agent processes artifacts from multiple sources (document retrieval, SQL queries, web search, etc.)
and generates a structured research answer with proper citations.
The arguments within the tags must be: 
1) instructions about what to look for in the data
2) the artefacts <artefact> ... </artefact> that describe what was found by the other agents above.

Output format: markdown table with columns
| paragraph | source |
| --- | --- |
| ... | ... |
        """