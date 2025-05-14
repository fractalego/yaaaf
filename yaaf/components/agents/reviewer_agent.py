import logging
import pandas as pd
import sklearn
import sys
import re
from io import StringIO
from typing import List, Optional

from yaaf.components.agents.artefact_utils import get_table_and_model_from_artefacts, \
    get_artefacts_from_utterance_content, create_prompt_from_artefacts
from yaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaf.components.agents.base_agent import BaseAgent
from yaaf.components.agents.prompts import (
    reviewer_agent_prompt_template_without_model,
    reviewer_agent_prompt_template_with_model,
)
from yaaf.components.agents.settings import task_completed_tag
from yaaf.components.client import BaseClient
from yaaf.components.data_types import Messages, Utterance

_logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```python"
    _stop_sequences = _completing_tags
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client

    async def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
    ) -> str:
        last_utterance = messages.utterances[-1]
        artefact_list: List[Artefact] = get_artefacts_from_utterance_content(
            last_utterance.content
        )
        if not artefact_list:
            return "No artefacts was given"

        messages = messages.add_system_prompt(
            create_prompt_from_artefacts(
                artefact_list,
                "dummy_filename",
                reviewer_agent_prompt_template_with_model,
                reviewer_agent_prompt_template_without_model,
            )
        )


        messages = messages.add_system_prompt(
            self._create_prompt_from_artefacts(artefact_list)
        )
        df, model = get_table_and_model_from_artefacts(artefact_list)
        code_result = "no code could be executed"
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            messages.add_assistant_utterance(answer)
            matches = re.findall(
                rf"{self._output_tag}(.+)(```)?",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            if matches:
                code = matches[0][0]
                try:
                    old_stdout = sys.stdout
                    redirected_output = sys.stdout = StringIO()
                    global_variables = globals().copy()
                    global_variables.update({"dataframe": df, "sklearn_model": model})
                    exec(code, global_variables)
                    sys.stdout = old_stdout
                    code_result = redirected_output.getvalue()
                    if code_result.strip() == "":
                        code_result = "The code executed successfully but no output was generated."
                except Exception as e:
                    print(e)
                    code_result = f"Error while executing the code above.\nThis exception is raised {str(e)}"

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

    def get_description(self) -> str:
        return f"""
Reviewer agent: This agent is given the relevant artefact table and searches for a specific piece of information.
To call this agent write {self.get_opening_tag()} ENGLISH INSTRUCTIONS AND ARTEFACTS THAT DESCRIBE WHAT TO RETRIEVE FROM THE DATA {self.get_closing_tag()}
This agent is called when you need to check if the output of the sql agent answers the oevarching goal.
The arguments within the tags must be: a) instructions about what to look for in the data 2) the artefacts <artefact> ... </artefact> that describe were found by the other agents above (both tables and models).
Do *not* use images in the arguments of this agent.
        """

    def get_opening_tag(self) -> str:
        return "<revieweragent>"

    def get_closing_tag(self) -> str:
        return "</revieweragent>"

    def _create_prompt_from_artefacts(self, artefact_list: List[Artefact]) -> str:
        table_artefacts = [
            item
            for item in artefact_list
            if item.type == Artefact.Types.TABLE or item.type == Artefact.Types.IMAGE
        ]
        models_artefacts = [
            item for item in artefact_list if item.type == Artefact.Types.MODEL
        ]
        if not table_artefacts and not models_artefacts:
            raise ValueError("No artefacts found in the message.")
        if not table_artefacts:
            table_artefacts = [pd.DataFrame()]

        if not models_artefacts:
            return reviewer_agent_prompt_template_without_model.complete(
                data_source_name="dataframe",
                data_source_type=str(type(table_artefacts[0].data)),
                schema=table_artefacts[0].description,
            )

        return reviewer_agent_prompt_template_with_model.complete(
            data_source_name="dataframe",
            data_source_type=str(type(table_artefacts[0].data)),
            schema=table_artefacts[0].description,
            model_name="sklearn_model",
            sklearn_model=models_artefacts[0].model,
            training_code=models_artefacts[0].code,
        )
