import re
from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages
from yaaaf.components.agents.prompts import reflection_agent_prompt_template


class ReflectionAgent(BaseAgent):
    _system_prompt: PromptTemplate = reflection_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```text"
    _stop_sequences = []
    _max_steps = 5

    def __init__(self, client: BaseClient) -> None:
        self._client = client

    async def query(
        self, messages: Messages, notes: Optional[List[str]] = None
    ) -> str:
        messages = messages.add_system_prompt(self._system_prompt.complete())
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

    def get_description(self) -> str:
        return f"""
Self-reflection agent: This agent thinks step by step about the actions to take.
Use it when you need to think about the task.
Inform the agent about the tools at your disposal (SQL and Visualization).
To call this agent write {self.get_opening_tag()} THINGS TO THINK ABOUT {self.get_closing_tag()}
        """

