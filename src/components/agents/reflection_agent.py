import re
from typing import List, Optional

from src.components.agents.base_agent import BaseAgent
from src.components.client import BaseClient
from src.components.data_types import PromptTemplate, Messages
from src.components.agents.prompts import reflection_agent_prompt_template


class ReflectionAgent(BaseAgent):
    _system_prompt: PromptTemplate = reflection_agent_prompt_template
    _completing_tags: List[str] = ["COMPLETED_TASK"]
    _output_tag = "```output"
    _stop_sequences = ["COMPLETED_TASK"]
    _max_steps = 5

    def __init__(self, client: BaseClient) -> None:
        self._client = client

    def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
    ) -> str:
        messages = messages.add_system_prompt(self._system_prompt.complete())
        current_output: str = "No output"
        for _ in range(self._max_steps):
            answer = self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            if self.is_complete(answer) or answer.strip() == "":
                break

            messages = messages.add_assistant_utterance(
                f"The answer is:\n\n{answer}\n\nThink if you need to do more otherwise output {self._completing_tags[0]}.\n"
            )
            matches = re.findall(
                rf"{self._output_tag}(.+)$",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            if matches:
                current_output = matches[0]

        return current_output

    def get_description(self) -> str:
        return """
Self-reflection agent: This agent thinks step by step about the actions to take.
Use it when you need to think about the task.
Inform the agent about the tools at your disposal (SQL and Visualization).
To call this agent write ```self-reflection-agent THINGS TO THINK ABOUT ```
        """

    def get_opening_tag(self) -> str:
        return "```self-reflection-agent"

    def get_closing_tag(self) -> str:
        return "```"
