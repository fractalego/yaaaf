import os
import re

from typing import Optional, List, Callable
from src.components.agents.base_agent import BaseAgent
from src.components.client import BaseClient
from src.components.data_types import Messages, PromptTemplate
from src.components.agents.prompts import sql_agent_prompt_template
from src.components.sources.sqlite_source import SqliteSource

_path = os.path.dirname(os.path.abspath(__file__))


class SqlAgent(BaseAgent):
    _system_prompt: PromptTemplate = sql_agent_prompt_template
    _completing_tags: List[str] = ["<task-completed/>"]
    _output_tag = "```sql"
    _stop_sequences = ["<task-completed/>"]
    _max_steps = 5

    def __init__(self, client: BaseClient, source: SqliteSource):
        self._schema = source.get_description()
        self._client = client
        self._source = source

    def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
    ) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(schema=self._schema)
        )
        current_output: str = "No output"
        for _ in range(self._max_steps):
            answer = self._client.predict(
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

        return current_output

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
