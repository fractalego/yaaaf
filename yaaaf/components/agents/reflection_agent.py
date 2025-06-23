import re
from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages, Note
from yaaaf.components.agents.prompts import reflection_agent_prompt_template
from yaaaf.components.decorators import handle_exceptions


class ReflectionAgent(BaseAgent):
    _system_prompt: PromptTemplate = reflection_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```text"
    _stop_sequences = []
    _max_steps = 5

    def __init__(
        self, client: BaseClient, agents_and_sources_and_tools_list: str = ""
    ) -> None:
        self._client = client
        self._agents_and_sources_and_tools_list = agents_and_sources_and_tools_list

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
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
            if notes is not None and step_idx > 0:  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Reflection Step {step_idx}] {answer}",
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

            messages = messages.add_user_utterance(
                f"The answer is:\n\n{answer}\n\nIf it is satisfactory output {self._completing_tags[0]} at the beginning of your answer and nothing else.\n"
            )
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
        return "This agent thinks step by step about the actions to take"

    def get_description(self) -> str:
        return f"""
Self-reflection agent: {self.get_info()}.
Always call this agent first to think about the task and plan the next steps.
Call this agent only once per task, it is not meant to be called multiple times.
To call this agent write {self.get_opening_tag()} THINGS TO THINK ABOUT {self.get_closing_tag()}
        """
