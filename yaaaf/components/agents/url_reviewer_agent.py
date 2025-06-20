import logging
import mdpd
from typing import List, Optional

import pandas as pd

from yaaaf.components.agents.artefact_utils import (
    get_table_and_model_from_artefacts,
    get_artefacts_from_utterance_content,
)
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.prompts import (
    url_retriever_agent_prompt_template_without_model,
)
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.texts import no_artefact_text
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class UrlReviewerAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```table"
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

        df, _ = get_table_and_model_from_artefacts(artefact_list)
        messages = messages.add_system_prompt(
            url_retriever_agent_prompt_template_without_model.complete(
                table=df.to_markdown(index=False),
            )
        )
        output_df: pd.DataFrame = pd.DataFrame()
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            messages.add_assistant_utterance(answer)
            output = get_first_text_between_tags(answer, self._output_tag, "```")
            if output.strip() != "":
                output_df = mdpd.from_md(output)

            if self.is_complete(answer) or answer.strip() == "":
                break

            messages.add_assistant_utterance(
                f"The result is <result>{output}</result>. If there the initial query {last_utterance} is answered write {self._completing_tags[0]} at the beginning of your answer.\n"
                f"If there are errors try to correct them in the next steps.\n"
            )
        if output_df.empty:
            return "Could not find a result in the artefacts. Please try again with a different query."

        hash_id: str = str(hash(str(messages))).replace("-", "")
        self._storage.store_artefact(
            hash_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description=str(messages),
                data=output_df,
                id=hash_id,
            ),
        )
        return f"The result is in this artefact <artefact type='paragraphs-table'>{hash_id}</artefact>"

    @staticmethod
    def get_info() -> str:
        return "This agent is given the relevant artefact table of web search results and retrieves the relevant information from these results."

    def get_description(self) -> str:
        return f"""
Url Retriever agent: {self.get_info()}
To call this agent write {self.get_opening_tag()} ENGLISH QUERY AND ARTEFACTS THAT DESCRIBE WHAT TO RETRIEVE FROM THE WEB SEARCH RESULTS {self.get_closing_tag()}
This agent is called when you need to better look into the content of a url.
The arguments within the tags must be: a) instructions about what to look for in the data 2) the artefacts <artefact> ... </artefact> that describe were found by the other agents above (only websearch results.
Do *not* use images in the arguments of this agent.
        """
