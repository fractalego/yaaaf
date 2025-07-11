from typing import List, Optional
from io import StringIO

import pandas as pd

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages, Note
from yaaaf.components.agents.prompts import todo_agent_prompt_template
from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.decorators import handle_exceptions


class TodoAgent(BaseAgent):
    _system_prompt: PromptTemplate = todo_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```table"
    _stop_sequences = []
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(
        self, client: BaseClient, agents_and_sources_and_tools_list: str = ""
    ) -> None:
        super().__init__()
        self.set_budget(1)  # TodoAgent only gets 1 call per query
        self._client = client
        self._agents_and_sources_and_tools_list = agents_and_sources_and_tools_list

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

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(
                agents_and_sources_and_tools_list=self._agents_and_sources_and_tools_list
            )
        )
        current_output: str = "No output"
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
                    message=f"[Todo Planning Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            if (
                self._output_tag not in answer and self.is_complete(answer)
            ) or answer.strip() == "":
                break

            # Add internal note for agent's intermediate message
            feedback_message = f"The todo list is:\n\n{answer}\n\nIf it is satisfactory output {self._completing_tags[0]} at the beginning of your answer and nothing else.\n"
            self._add_internal_message(feedback_message, notes, "Todo Feedback")
            messages = messages.add_user_utterance(feedback_message)
            current_output = get_first_text_between_tags(
                answer, self._output_tag, "```"
            )
            if not current_output:
                current_output = get_first_text_between_tags(answer, "```", "```")

        # Parse the markdown table into a DataFrame and create artifact
        try:
            markdown_table = current_output.replace(task_completed_tag, "").strip()

            # Parse markdown table into DataFrame
            lines = [
                line.strip() for line in markdown_table.split("\n") if line.strip()
            ]
            if len(lines) >= 3:  # Header, separator, and at least one data row
                # Extract header
                header_line = lines[0]
                headers = [col.strip() for col in header_line.split("|") if col.strip()]

                # Extract data rows (skip separator line)
                data_rows = []
                for line in lines[2:]:  # Skip header and separator
                    row = [col.strip() for col in line.split("|") if col.strip()]
                    if len(row) == len(headers):
                        data_rows.append(row)

                if data_rows:
                    df = pd.DataFrame(data_rows, columns=headers)

                    # Create and store the todo-list artifact
                    df_info_output = StringIO()
                    table_id = create_hash(df.to_markdown())
                    df.info(verbose=True, buf=df_info_output)
                    self._storage.store_artefact(
                        table_id,
                        Artefact(
                            type=Artefact.Types.TODO_LIST,
                            data=df,
                            description=df_info_output.getvalue(),
                            code=None,
                            id=table_id,
                        ),
                    )
                    return f"Todo list created and stored in this artifact <artefact type='todo-list'>{table_id}</artefact>."
        except Exception:
            # Fallback to original behavior if parsing fails
            pass

        return current_output.replace(task_completed_tag, "")

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent creates structured todo lists for planning query responses"

    def get_description(self) -> str:
        return f"""
Todo planning agent: {self.get_info()}.
Always call this agent first to create a structured todo list and plan the next steps.
Call this agent only once per task, it is not meant to be called multiple times.
Budget: {self.get_budget()} call remaining.
Provide the query that needs to be planned and organized into actionable steps.
        """
