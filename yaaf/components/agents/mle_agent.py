import logging
import os
import sys
import re
import sklearn
import numpy as np
import pandas as pd

from io import StringIO
from typing import List, Dict, Optional, Tuple

from yaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaf.components.agents.base_agent import BaseAgent
from yaaf.components.agents.settings import task_completed_tag
from yaaf.components.client import BaseClient
from yaaf.components.data_types import Messages, Utterance
from yaaf.components.agents.prompts import mle_agent_prompt_template_without_model

_logger = logging.getLogger(__name__)


class MleAgent(BaseAgent):
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
        artefact_list: List[Artefact] = self._get_artefacts(last_utterance)
        if not artefact_list:
            return "No artefacts was given"

        messages = messages.add_system_prompt(
            self._create_prompt_from_artefacts(artefact_list)
        )
        df, model = self._get_table_and_model_from_artefacts(artefact_list)
        hash_string: str = str(hash(str(messages))).replace("-", "")
        model_name: str = hash_string + ".png"
        messages = messages.add_system_prompt(
            self._create_prompt_from_artefacts(artefact_list, model_name)
        )
        df, model = self._get_table_and_model_from_artefacts(artefact_list)
        code = ""
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            messages.add_assistant_utterance(answer)
            matches = re.findall(
                rf"{self._output_tag}(.+)```",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            code_result = "No code found"
            if matches:
                code = matches[0]
                try:
                    old_stdout = sys.stdout
                    redirected_output = sys.stdout = StringIO()
                    global_variables = globals().copy()
                    global_variables.update({"dataframe": df, "sklearn_model": model})
                    exec(code)
                    sys.stdout = old_stdout
                    code_result = redirected_output.getvalue()
                    if code_result.strip() == "":
                        code_result = ""
                except Exception as e:
                    print(e)
                    code_result = f"Error while executing the code above.\nThis exception is raised {str(e)}"
                    answer = str(code_result)

            if (
                self.is_complete(answer)
                or answer.strip() == ""
                or code_result.strip() == ""
            ):
                break

            messages.add_assistant_utterance(
                f"The result is: {code_result}. If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
            )

        if os.path.exists(model_name):
            self._storage.store_artefact(
                hash_string,
                Artefact(
                    type=Artefact.Types.MODEL,
                    description=str(messages),
                    code=code,
                    data=df,
                    id=hash_string,
                ),
            )
            os.remove(model_name)
        return f"The result is in this artefact <artefact type='model'>{hash_string}</artefact>"


    def get_description(self) -> str:
        return f"""
Visualization agent: This agent creates the relevant visualization in the format of a graph plot using a markdown table.
To call this agent write {self.get_opening_tag()} MARKDOWN TABLE ABOUT WHAT TO PLOT {self.get_closing_tag()}
The information about what to plot will be then used by the agent.
        """

    def get_opening_tag(self) -> str:
        return "<mleagent>"

    def get_closing_tag(self) -> str:
        return "</mleagent>"

    def _get_artefacts(self, last_utterance: Utterance) -> List[Artefact]:
        artefact_matches = re.findall(rf"<artefact>(.+?)</artefact>", last_utterance.content, re.MULTILINE|re.DOTALL)
        if not artefact_matches:
            return []

        artefacts: List[Artefact] = []
        for match in artefact_matches:
            artefact_id: str = match
            try:
                artefacts.append(self._storage.retrieve_from_id(artefact_id))
            except ValueError:
                pass

        return artefacts

    def _create_prompt_from_artefacts(self, artefact_list: List[Artefact], filename: str) -> str:
        table_artefacts = [
            item for item in artefact_list if item.type == Artefact.Types.TABLE or item.type == Artefact.Types.IMAGE
        ]
        models_artefacts = [
            item for item in artefact_list if item.type == Artefact.Types.MODEL
        ]
        if not table_artefacts:
            table_artefacts = [
                Artefact(
                    data=pd.DataFrame(),
                    description="",
                    type=Artefact.Types.TABLE,
                )
            ]

        if not models_artefacts:
            return mle_agent_prompt_template_without_model.complete(
                data_source_name="dataframe",
                data_source_type=str(type(table_artefacts[0].data)),
                schema=table_artefacts[0].description,
                filename=filename,
            )

        return mle_agent_prompt_template_without_model.complete(
            data_source_name="dataframe",
            data_source_type=str(type(table_artefacts[0].data)),
            schema=table_artefacts[0].description,
            model_name="sklearn_model",
            sklearn_model=models_artefacts[0].model,
            training_code=models_artefacts[0].code,
            filename=filename,
        )

    def _get_table_and_model_from_artefacts(self, artefact_list: List[Artefact]) -> Tuple[pd.DataFrame, sklearn.base.BaseEstimator]:
        table_artefacts = [
            item for item in artefact_list if item.type == Artefact.Types.TABLE or item.type == Artefact.Types.IMAGE
        ]
        models_artefacts = [
            item for item in artefact_list if item.type == Artefact.Types.MODEL
        ]
        return table_artefacts[0].data if table_artefacts else None, models_artefacts[0].model if models_artefacts else None