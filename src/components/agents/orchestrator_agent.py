import re
from typing import List, Tuple, Optional

from src.components.agents.base_agent import BaseAgent
from src.components.client import BaseClient
from src.components.data_types import Messages
from src.components.agents.prompts import orchestrator_prompt_template
from src.components.extractors.goal_extractor import GoalExtractor


class OrchestratorAgent(BaseAgent):
    _system_prompt: str = orchestrator_prompt_template
    _completing_tags: List[str] = ["<task-completed/>"]
    _agents_map: {str: BaseAgent} = {}
    _stop_sequences = []
    _max_steps = 10
    _goal_extractor = GoalExtractor()

    def __init__(self, client: BaseClient):
        self._client = client
        self._agents_map = {
            key: agent(client) for key, agent in self._agents_map.items()
        }

    def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
    ) -> str:
        goal = self._goal_extractor.extract_goal(messages)
        self._system_prompt = self._system_prompt.complete(
            goal=goal,
        )
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
                messages = messages.add_assistant_utterance(
                    f"Calling {agent_to_call.get_name()} with instruction:\n\n{instruction}\n\n"
                )
                answer = agent_to_call.query(
                    Messages().add_user_utterance(instruction),
                    message_queue=message_queue,
                )
                if message_queue is not None:
                    message_queue.append(agent_to_call.clean_answer(answer))
                messages = messages.add_user_utterance(
                    f"The answer from the agent is:\n\n{answer}\n\nWhen you are 100% sure about the answer and the task is done, write the tag {self._completing_tags[0]}."
                )
            else:
                messages = messages.add_assistant_utterance(answer)
                messages = messages.add_user_utterance(
                    f"You didn't call any agent. Is the answer finished or did you miss outputting the tags? Reminder: use the relevant html tags to call the agents.\n\n"
                )
        if not self.is_complete(answer) and step_index == self._max_steps - 1:
            answer += "\nThe Orchestrator agent has finished its maximum number of steps. <task-completed/>"
        return answer

    def subscribe_agent(self, agent: BaseAgent):
        if agent.get_opening_tag() in self._agents_map:
            raise ValueError(
                f"Agent with tag {agent.get_opening_tag()} already exists."
            )
        self._agents_map[agent.get_opening_tag()] = agent
        self._stop_sequences.append(agent.get_closing_tag())
        self._system_prompt = orchestrator_prompt_template.complete(
            agents_list="\n".join(
                [
                    "* " + agent.get_description().strip() + "\n"
                    for agent in self._agents_map.values()
                ]
            ),
            all_tags_list="\n".join(
                [
                    agent.get_opening_tag().strip() + agent.get_closing_tag().strip()
                    for agent in self._agents_map.values()
                ]
            ),
        )

    def map_answer_to_agent(self, answer: str) -> Tuple[BaseAgent | None, str]:
        for tag, agent in self._agents_map.items():
            if tag in answer:
                matches = re.findall(
                    rf"{agent.get_opening_tag()}(.+)", answer, re.DOTALL | re.MULTILINE
                )
                if matches:
                    return agent, matches[0]

        return None, ""

    def get_description(self) -> str:
        return """
Orchestrator agent: This agent orchestrates the agents.
        """

    def get_opening_tag(self) -> str:
        return "<orchestrator-agent>"

    def get_closing_tag(self) -> str:
        return "</orchestrator-agent>"
