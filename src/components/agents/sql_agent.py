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
    _completing_tags: List[str] = ["<complete/>"]
    _output_tag = "<sql_call>"
    _stop_sequences = ["<complete/>", "</sql_call>"]
    _max_steps = 5

    def __init__(self, client: BaseClient, source: SqliteSource):
        self._schema = source.get_sql_schema()
        self._client = client
        self._source = source

    def query(self, messages: Messages, message_queue: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt.complete(schema=self._schema))
        current_output: str = "No output"
        for _ in range(self._max_steps):
            answer = self._client.predict(messages=messages, stop_sequences=self._stop_sequences)
            if self.is_complete(answer):
                break

            matches = re.findall(
                rf"{self._output_tag}(.+?){self._output_tag.replace('<', '</')}",
                answer,
                re.DOTALL|re.MULTILINE,
            )
            if not matches:
                matches = re.findall(
                    rf"```sql(.+?)```",
                    answer,
                    re.DOTALL | re.MULTILINE,
                )
            if matches:
                sql_query = matches[0]
                message_queue.append(f"```SQL\n{sql_query}\n```")
                current_output = self._source.get_data(sql_query)
                messages = messages.add_assistant_utterance(
                    f"The answer is {answer}.\n\nThe output of this SQL query is {current_output}.\n\n\n"
                    f"If there are no errors write {self._completing_tags[0]}.\n"
                    f"If there are errors correct the SQL query accordingly."
                )
            else:
                messages = messages.add_assistant_utterance(
                    f"The answer is {answer} but there is no SQL call. Try again. If there are errors correct the SQL query accordingly."
                )

        return current_output

