import logging
import os
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
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.texts import no_artefact_text
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages
from yaaaf.components.agents.prompts import (
    mle_agent_prompt_template_without_model,
    mle_agent_prompt_template_with_model,
)
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class MleAgent(BaseAgent):
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

        hash_string: str = create_hash(str(messages))
        model_name: str = hash_string + ".png"
        messages = messages.add_system_prompt(
            create_prompt_from_artefacts(
                artefact_list,
                model_name,
                mle_agent_prompt_template_with_model,
                mle_agent_prompt_template_without_model,
            )
        )
        df, model = get_table_and_model_from_artefacts(artefact_list)
        code = ""
        code_result = "No code found"
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
                    code_result = ""

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
        return (
            f"The result is in this artefact <artefact type='model'>{hash_string}</artefact>"
            f"Additionally, the model returned the output {code_result}.\n"
        )

    @staticmethod
    def get_info() -> str:
        return "This agent is given the relevant table, quickly trains a small sklearn model and saves it in a joblib file."

    def get_description(self) -> str:
        return f"""
Visualization agent: {self.get_info()}
You can use linear interpolation, polynomial regression, SVM, logistic regression, decision trees, random forests.
To call this agent write {self.get_opening_tag()} ENGLISH INSTRUCTIONS AND ARTEFACTS THAT DESCRIBE WHAT TO APPLY THE SKLEARN MODEL TO {self.get_closing_tag()}
The arguments within the tags must be: a) instructions about what to look for in the data 2) the artefacts <artefact> ... </artefact> that describe were found by the other agents above (both tables and models).
The information about what to plot will be then used by the agent.
        """
