import logging
import os
from io import StringIO

from typing import Optional, List

import pandas as pd

from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate, Note
from yaaaf.components.agents.prompts import sql_agent_prompt_template
from yaaaf.components.sources.sqlite_source import SqliteSource
from yaaaf.components.decorators import handle_exceptions

_path = os.path.dirname(os.path.abspath(__file__))
_logger = logging.getLogger(__name__)


class SqlAgent(BaseAgent):
    _system_prompt: PromptTemplate = sql_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```sql"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient, sources: List[SqliteSource]):
        super().__init__()
        self._client = client
        self._sources = sources
        # Create combined schema description from all sources
        self._schema = "\n\n".join([
            f"Database: {source.name}\nPath: {source.db_path}\n{source.get_description()}"
            for source in sources
        ])

    def _add_internal_message(
        self, message: str, notes: Optional[List[Note]], prefix: str = "Message"
    ):
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

    def _execute_query_on_sources(self, sql_query: str) -> pd.DataFrame:
        """Execute SQL query on the appropriate source(s)."""
        # If there's only one source, use it directly
        if len(self._sources) == 1:
            return self._sources[0].get_data(sql_query)
        
        # Try to find table references in the query to determine which database to use
        query_lower = sql_query.lower()
        
        # Try each source and return the first successful result
        last_error = None
        for source in self._sources:
            try:
                result = source.get_data(sql_query)
                # Check if we got a valid result (not an error DataFrame)
                if not (len(result.columns) == 2 and 'Errors' in result.columns and 'Results' in result.columns):
                    return result
                else:
                    last_error = result
            except Exception as e:
                continue
        
        # If no source worked, return the last error or a generic error
        if last_error is not None:
            return last_error
        else:
            return pd.DataFrame.from_dict({
                "Errors": ["Query failed on all available databases"],
                "Results": ["No results found"]
            })

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(schema=self._schema)
        )
        current_output: str | pd.DataFrame = "No output"
        sql_query = "No SQL query"
        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            answer = response.message

            # Log internal thinking step
            if (
                notes is not None and step_idx > 0
            ):  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Internal Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            if self.is_complete(answer) or answer.strip() == "":
                break

            sql_query = get_first_text_between_tags(answer, self._output_tag, "```")
            if sql_query:
                if notes is not None:
                    model_name = getattr(self._client, "model", None)
                    note = Note(
                        message=f"\n\n```SQL\n{sql_query}\n```\n\n",
                        artefact_id=None,
                        agent_name=self.get_name(),
                        model_name=model_name,
                    )
                    notes.append(note)
                current_output = self._execute_query_on_sources(sql_query)
                feedback_message = (
                    f"The answer is {answer}.\n\nThe output of this SQL query is {current_output}.\n\n\n"
                    f"If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"If there are errors correct the SQL query accordingly you will need to write the SQL query leveraging the schema above.\n"
                )
                self._add_internal_message(feedback_message, notes, "SQL Feedback")
                messages = messages.add_user_utterance(feedback_message)
            else:
                error_message = f"The answer is {answer} but there is no SQL call. Try again. If there are errors correct the SQL query accordingly."
                self._add_internal_message(error_message, notes, "SQL Error")
                messages = messages.add_user_utterance(error_message)

        df_info_output = StringIO()
        table_id = create_hash(current_output.to_markdown())
        current_output.info(verbose=True, buf=df_info_output)
        self._storage.store_artefact(
            table_id,
            Artefact(
                type=Artefact.Types.TABLE,
                data=current_output,
                description=df_info_output.getvalue(),
                code=sql_query,
                id=table_id,
            ),
        )
        return f"The result is in this artifact <artefact type='table'>{table_id}</artefact>."

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent calls the relevant sql table and outputs the results"

    def get_description(self) -> str:
        return f"""
SQL agent: {self.get_info()}.
This agent provides an interface to a dataset through SQL queries. It includes table information and column names.
To call this agent write {self.get_opening_tag()} INFORMATION TO RETRIEVE {self.get_closing_tag()}
Do not write an SQL formula. Just write in clear and brief English the information you need to retrieve.
        """
