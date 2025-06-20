from typing import List, Optional

from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.agents.prompts import user_input_agent_prompt_template
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import PromptTemplate, Messages
from yaaaf.components.decorators import handle_exceptions


class UserInputAgent(BaseAgent):
    _system_prompt: PromptTemplate = user_input_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag, task_paused_tag]
    _output_tag = "```question"
    _stop_sequences = [task_completed_tag, task_paused_tag]
    _max_steps = 5

    def __init__(self, client: BaseClient) -> None:
        self._client = client

    def is_paused(self, answer: str) -> bool:
        """Check if the agent has paused execution to wait for user input."""
        return task_paused_tag in answer

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        current_output = "No output"
        user_question = ""

        for step in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

            # Handle empty responses
            if answer.strip() == "":
                break

            # Check if agent is asking a question to pause for user input
            question = get_first_text_between_tags(answer, self._output_tag, "```")

            if question:
                user_question = question.strip()
                # Return the question with paused tag to signal frontend
                return f"{user_question} {task_paused_tag}"

            # If no question format found but contains paused tag, extract the question
            if self.is_paused(answer):
                # Extract question from the answer (before the paused tag)
                question_part = answer.split(task_paused_tag)[0].strip()
                return f"{question_part} {task_paused_tag}"

            # Check if completed with task_completed_tag
            if task_completed_tag in answer:
                current_output = answer.replace(task_completed_tag, "").strip()
                break

            # Continue the conversation if no pause or completion
            messages = messages.add_user_utterance(
                f"Your response: {answer}\n\n"
                f"If you need more information from the user, ask a specific question using the ```question format and then use {task_paused_tag}.\n"
                f"If you have enough information to complete the task, provide your final answer and use {task_completed_tag}."
            )

            # Extract any regular output
            current_output = answer

        # Clean up the final output
        final_output = current_output.replace(task_paused_tag, "").strip()
        return final_output

    @staticmethod
    def get_info() -> str:
        return "This agent can interact with the user to gather additional information needed to complete requests."

    def get_description(self) -> str:
        return f"""
User Input agent: {self.get_info()}
Use this agent when you need clarification, preferences, or additional details from the user.
The agent will pause execution and wait for user responses when needed.
To call this agent write {self.get_opening_tag()} TASK_THAT_NEEDS_USER_INPUT {self.get_closing_tag()}
The agent can ask questions and pause the workflow until the user provides answers.
        """
