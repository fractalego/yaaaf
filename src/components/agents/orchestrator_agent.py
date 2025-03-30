import re
from typing import List, Tuple, Callable, Optional

from src.components.agents.base_agent import BaseAgent
from src.components.client import BaseClient
from src.components.data_types import Messages
from src.components.agents.prompts import orchestrator_prompt_template


class OrchestratorAgent(BaseAgent):
    _system_prompt: str = orchestrator_prompt_template
    _completing_tags: List[str] = ["COMPLETED_TASK"]
    _agents_map: {str: BaseAgent} = {}
    _stop_sequences = _completing_tags.copy()
    _max_steps = 5

    def __init__(self, client: BaseClient):
        self._client = client
        self._agents_map = {
            key: agent(client) for key, agent in self._agents_map.items()
        }

    def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
    ) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        answer: str = ""
        for step_index in range(self._max_steps):
            answer = self._client.predict(messages, stop_sequences=self._stop_sequences)
            if message_queue is not None:
                message_queue.append(answer)
            if self.is_complete(answer) or answer.strip() == "":
                break
            agent_to_call, instruction = self.map_answer_to_agent(answer)
            if agent_to_call is not None:
                messages = messages.add_assistant_utterance(f"Calling {agent_to_call.get_name()} with instruction:\n\n{instruction}\n\n")
                answer = agent_to_call.query(
                    Messages().add_user_utterance(instruction),
                    message_queue=message_queue,
                )
                if message_queue is not None:
                    message_queue.append(agent_to_call.clean_answer(answer))
            messages = messages.add_assistant_utterance(
                f"The answer from the agent is:\n\n{answer}\n\n"
            )
        if not self.is_complete(answer) and step_index == self._max_steps - 1:
            answer += "\nThe Orchestrator agent has finished its maximum number of steps. COMPLETED_TASK"
        return answer

    def subscribe_agent(self, agent: BaseAgent):
        if agent.get_opening_tag() in self._agents_map:
            raise ValueError(
                f"Agent with tag {agent.get_opening_tag()} already exists."
            )
        self._agents_map[agent.get_opening_tag()] = agent
        self._system_prompt = orchestrator_prompt_template.complete(
            agents_list="\n".join(
                [
                    "* " + agent.get_description().strip() + "\n"
                    for agent in self._agents_map.values()
                ]
            )
        )

    def map_answer_to_agent(self, answer: str) -> Tuple[BaseAgent | None, str]:
        for tag, agent in self._agents_map.items():
            if tag in answer:
                matches = re.findall(rf"{tag}(.+)$", answer, re.DOTALL | re.MULTILINE)
                if matches:
                    return agent, matches[0]

        return None, ""

    def get_description(self) -> str:
        return """
Orchestrator agent: This agent orchestrates the agents.
        """

    def get_opening_tag(self) -> str:
        return "```orchestrator-agent"

    def get_closing_tag(self) -> str:
        return "```"
