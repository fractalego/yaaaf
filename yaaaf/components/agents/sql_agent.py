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

    def __init__(self, client: BaseClient, source: SqliteSource):
        self._schema = source.get_description()
        self._client = client
        self._source = source

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(schema=self._schema)
        )
        current_output: str | pd.DataFrame = "No output"
        sql_query = "No SQL query"
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            if self.is_complete(answer) or answer.strip() == "":
                break

            sql_query = get_first_text_between_tags(answer, self._output_tag, "```")
            if sql_query:
                if notes is not None:
                    model_name = getattr(self._client, "model", None)
                    note = Note(
                        message=f"```SQL\n{sql_query}\n```",
                        artefact_id=None,
                        agent_name=self.get_name(),
                        model_name=model_name,
                    )
                    notes.append(note)
                current_output = self._source.get_data(sql_query)
                messages = messages.add_user_utterance(
                    f"The answer is {answer}.\n\nThe output of this SQL query is {current_output}.\n\n\n"
                    f"If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"If there are errors correct the SQL query accordingly you will need to write the SQL query leveraging the schema above.\n"
                )
            else:
                messages = messages.add_user_utterance(
                    f"The answer is {answer} but there is no SQL call. Try again. If there are errors correct the SQL query accordingly."
                )

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
