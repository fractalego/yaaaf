import re
from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages, Note
from yaaaf.components.agents.prompts import todo_agent_prompt_template
from yaaaf.components.decorators import handle_exceptions


class TodoAgent(BaseAgent):
    _system_prompt: PromptTemplate = todo_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```json"
    _stop_sequences = []
    _max_steps = 5

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
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

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
            matches = re.findall(
                rf"{self._output_tag}(.+)```",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            if matches:
                current_output = matches[0]

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
To call this agent write {self.get_opening_tag()} QUERY TO PLAN {self.get_closing_tag()}
        """
