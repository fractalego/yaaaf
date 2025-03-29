import re
from typing import List, Tuple, Callable, Optional

from src.components.agents.base_agent import BaseAgent
from src.components.client import BaseClient
from src.components.data_types import Messages
from src.components.agents.prompts import orchestrator_prompt_template
from src.components.agents.reflection_agent import ReflectionAgent
from src.components.agents.sql_agent import SqlAgent
from src.components.agents.visualization_agent import VisualizationAgent


class OrchestratorAgent(BaseAgent):
    _system_prompt: str = orchestrator_prompt_template
    _completing_tags: List[str] = ["<complete/>"]
    _agents_map: {str: BaseAgent} = {
        "<sql_agent>": SqlAgent,
        "<visualization_agent>": VisualizationAgent,
        "<self_reflection_agent>": ReflectionAgent,
    }
    _stop_sequences = _completing_tags + [
        key.replace("<", "</") for key in _agents_map.keys()
    ]
    _max_steps = 5

    def __init__(self, client: BaseClient):
        self._client = client
        self._agents_map = {
            key: agent(client) for key, agent in self._agents_map.items()
        }

    def query(self, messages: Messages, message_queue: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        answer: str = ""
        for _ in range(self._max_steps):
            answer = self._client.predict(messages, stop_sequences=self._stop_sequences)
            message_queue.append(answer)
            if self.is_complete(answer):
                break
            agent_to_call, instruction = self.map_answer_to_agent(answer)
            if agent_to_call is not None:
                messages = messages.add_assistant_utterance(f"Calling: {answer}")
                answer = agent_to_call.query(
                    Messages().add_user_utterance(instruction),
                    message_queue=message_queue,
                )
                message_queue.append(agent_to_call.clean_answer(answer))
            messages = messages.add_assistant_utterance(
                f"The answer is:\n\n{answer}\n\nIf you have achieved the goal given by the very first instruction, "
                f"otherwise continue to investigate."
            )
        if not self.is_complete(answer):
            answer += "\nThe Orchestrator agent has finished its maximum number of steps. <complete/>"
        return answer

    def subscribe_agent(self, agent: BaseAgent):


    def map_answer_to_agent(self, answer: str) -> Tuple[BaseAgent|None, str]:
        for tag, agent in self._agents_map.items():
            if tag in answer:
                matches = re.findall(
                    rf"{tag}(.+?){tag.replace('<', '</')}",
                    answer,
                    re.DOTALL | re.MULTILINE,
                )
                if matches:
                    return agent, matches[0]
                matches = re.findall(rf"{tag}(.*)$", answer, re.DOTALL | re.MULTILINE)
                if matches:
                    return agent, matches[0]

        return None, ""