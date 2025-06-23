import os
from io import StringIO

import pandas as pd

from duckduckgo_search import DDGS
from typing import Optional, List, Dict

from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.prompts import duckduckgo_search_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate, Note
from yaaaf.components.decorators import handle_exceptions

_path = os.path.dirname(os.path.abspath(__file__))


class DuckDuckGoSearchAgent(BaseAgent):
    _system_prompt: PromptTemplate = duckduckgo_search_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```text"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client

    def _add_internal_message(self, message: str, notes: Optional[List[Note]], prefix: str = "Message"):
        """Helper to add internal messages to notes"""
        if notes is not None:
            internal_note = Note(
                message=f"[{prefix}] {message}",
                artefact_id=None,
                agent_name=self.get_name(),
                model_name=getattr(self._client, "model", None),
                internal=True,
            )
            notes.append(internal_note)

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        search_query = ""
        current_output: str | pd.DataFrame = "No output"
        for step_idx in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            
            # Log internal thinking step
            if notes is not None and step_idx > 0:  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[DuckDuckGo Search Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)
            
            if self.is_complete(answer) or answer.strip() == "":
                break

            search_query: str = get_first_text_between_tags(
                answer, self._output_tag, "```"
            )
            query_results: List[Dict[str, str]] = DDGS().text(
                search_query, max_results=5
            )
            if query_results:
                current_output = pd.DataFrame(
                    [
                        [result["title"], result["body"], result["href"]]
                        for result in query_results
                    ],
                    columns=["Title", "Summary", "URL"],
                )

                feedback_message = f"The web search query was {answer}.\n\nThe result of this query is {current_output}.\n\n\n" \
                                   f"If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n" \
                                   f"If there are errors correct the query accordingly.\n"
                self._add_internal_message(feedback_message, notes, "Search Feedback")
                messages = messages.add_user_utterance(feedback_message)
            else:
                error_message = f"The query is {answer} but there are no results from the web search. Try again. If there are errors correct the query accordingly."
                self._add_internal_message(error_message, notes, "Search Error")
                messages = messages.add_user_utterance(error_message)

        if isinstance(current_output, str):
            return current_output.replace(task_completed_tag, "")

        df_info_output = StringIO()
        web_search_id = create_hash(str(messages))
        current_output.info(verbose=True, buf=df_info_output)
        self._storage.store_artefact(
            web_search_id,
            Artefact(
                type=Artefact.Types.TABLE,
                data=current_output,
                description=df_info_output.getvalue(),
                code=search_query,
                id=web_search_id,
            ),
        )
        return f"The result is in this artifact <artefact type='websearch-result'>{web_search_id}</artefact>."

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent calls a web search engine and outputs the results"

    def get_description(self) -> str:
        return f"""
Web Search agent: {self.get_info()}.
This agent provides an interface to web search engine.
To call this agent write {self.get_opening_tag()} INFORMATION TO RETRIEVE {self.get_closing_tag()}
Just write in clear and brief English the information you need to retrieve between these tags. 
        """
