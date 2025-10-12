import logging
import sys
from io import StringIO
from typing import List, Optional

from yaaaf.components.agents.artefact_utils import (
    get_table_and_model_from_artefacts,
    get_artefacts_from_utterance_content,
    create_prompt_from_artefacts,
)
from yaaaf.components.extractors.artefact_extractor import ArtefactExtractor
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.prompts import (
    reviewer_agent_prompt_template_without_model,
    reviewer_agent_prompt_template_with_model,
)
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.texts import no_artefact_text
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```python"
    _stop_sequences = _completing_tags
    _max_steps = 5
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

        messages = messages.add_system_prompt(
            create_prompt_from_artefacts(
                artefact_list,
                "dummy_filename",
                reviewer_agent_prompt_template_with_model,
                reviewer_agent_prompt_template_without_model,
            )
        )
        df, model = get_table_and_model_from_artefacts(artefact_list)
        code_result = "no code could be executed"
        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

            # Process response to create thinking artifacts

            clean_message, thinking_artifact_ref = self._process_client_response(
                response, notes
            )

            if thinking_artifact_ref:
                thinking_artifacts.append(thinking_artifact_ref)
            answer = clean_message

            # Log internal thinking step
            if (
                notes is not None and step_idx > 0
            ):  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Reviewer Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            messages.add_assistant_utterance(answer)
            code = get_first_text_between_tags(answer, self._output_tag, "```")
            if code:
                old_stdout = sys.stdout
                redirected_output = sys.stdout = StringIO()
                global_variables = globals().copy()
                global_variables.update({"dataframe": df, "sklearn_model": model})
                exec(code, global_variables)
                sys.stdout = old_stdout
                code_result = redirected_output.getvalue()
                if code_result.strip() == "":
                    code_result = (
                        "The code executed successfully but no output was generated."
                    )

            if (
                self.is_complete(answer)
                or answer.strip() == ""
                or code_result.strip() == ""
            ):
                break

            feedback_message = f"The result is: {code_result}. If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
            self._add_internal_message(feedback_message, notes, "Reviewer Feedback")
            messages.add_assistant_utterance(feedback_message)

        return code_result

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent is given the relevant artefact table and searches for a specific piece of information"

    def get_description(self) -> str:
        return f"""
Reviewer agent: {self.get_info()}.
To call this agent write {self.get_opening_tag()} ENGLISH INSTRUCTIONS AND ARTEFACTS THAT DESCRIBE WHAT TO RETRIEVE FROM THE DATA {self.get_closing_tag()}
This agent is called when you need to check if the output of the sql agent answers the overarching goal.
The arguments within the tags must be: a) instructions about what to look for in the data 2) the artefacts <artefact> ... </artefact> that describe were found by the other agents above (both tables and models).
Do *not* use images in the arguments of this agent.
        """
