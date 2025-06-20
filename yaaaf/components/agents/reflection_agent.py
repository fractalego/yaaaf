import re
from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages
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
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(
                agents_and_sources_and_tools_list=self._agents_and_sources_and_tools_list
            )
        )
        current_output: str = "No output"
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            if (
                self._output_tag not in answer and self.is_complete(answer)
            ) or answer.strip() == "":
                break

            messages = messages.add_user_utterance(
                f"The answer is:\n\n{answer}\n\nThink if you need to do more otherwise output {self._completing_tags[0]} at the beginning of your answer.\n"
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
To call this agent write {self.get_opening_tag()} THINGS TO THINK ABOUT {self.get_closing_tag()}
        """
