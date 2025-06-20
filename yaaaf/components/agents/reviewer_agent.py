import logging
import sys
from io import StringIO
from typing import List, Optional

from yaaaf.components.agents.artefact_utils import (
    get_table_and_model_from_artefacts,
    get_artefacts_from_utterance_content,
    create_prompt_from_artefacts,
)
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
from yaaaf.components.data_types import Messages
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```python"
    _stop_sequences = _completing_tags
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        last_utterance = messages.utterances[-1]
        artefact_list: List[Artefact] = get_artefacts_from_utterance_content(
            last_utterance.content
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
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
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

            messages.add_assistant_utterance(
                f"The result is: {code_result}. If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
            )

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
