import hashlib
import os
import re
from io import StringIO

from typing import Optional, List, Callable

import pandas as pd

from yaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaf.components.agents.base_agent import BaseAgent
from yaaf.components.agents.settings import task_completed_tag
from yaaf.components.client import BaseClient
from yaaf.components.data_types import Messages, PromptTemplate
from yaaf.components.agents.prompts import sql_agent_prompt_template
from yaaf.components.sources.sqlite_source import SqliteSource

_path = os.path.dirname(os.path.abspath(__file__))


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

    async def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
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

            matches = re.findall(
                rf"{self._output_tag}(.+)```",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            if matches:
                sql_query = matches[0].replace("```sql", "").replace("```", "")
                if message_queue is not None:
                    message_queue.append(f"```SQL\n{sql_query}\n```")
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
        table_id = hashlib.md5(current_output.to_markdown().encode()).hexdigest()
        current_output.info(verbose=True, buf=df_info_output)
        self._storage.store_artefact(
            table_id,
            Artefact(
                type=Artefact.Types.TABLE,
                data=current_output,
                description=df_info_output.getvalue(),
                code=sql_query,
            )
        )
        return f"The result is in this artiface <artefact type='table'>{table_id}</artefact>."

    def get_description(self) -> str:
        return f"""
SQL agent: This agent calls the relevant sql table and outputs the results.
This agent provides an interface to a dataset through SQL queries. It includes table information and column names.
To call this agent write {self.get_opening_tag()} INFORMATION TO RETRIEVE {self.get_closing_tag()}
Do not write an SQL formula. Just write in clear and brief English the information you need to retrieve.
Limit all the SQL calls to 20 rows.
        """

    def get_opening_tag(self) -> str:
        return "<sql-agent>"

    def get_closing_tag(self) -> str:
        return "</sql-agent>"
