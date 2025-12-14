import logging

from yaaaf.components.agents.base_agent import CustomAgent
from yaaaf.components.agents.prompts import user_input_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from typing import Optional, List

_logger = logging.getLogger(__name__)


class UserInputAgent(CustomAgent):
    """Agent that handles user interaction and input requests."""

    def __init__(self, client: BaseClient):
        """Initialize user input agent."""
        super().__init__(client)
        self._system_prompt = user_input_agent_prompt_template
        self._output_tag = "```question"
        self._completing_tags = [task_completed_tag, task_paused_tag]
        self._stop_sequences = [task_completed_tag, task_paused_tag]

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Handles user interaction and input requests"

    def get_description(self) -> str:
        return f"""
User Input agent: {self.get_info()}.
This agent can:
- Ask questions to the user
- Request clarification or additional information
- Pause workflow for user input
- Handle interactive conversations

To call this agent write {self.get_opening_tag()} INPUT_REQUEST {self.get_closing_tag()}
Describe what information you need from the user.
        """

    def is_paused(self, answer: str) -> bool:
        """Check if the agent has paused execution to wait for user input."""
        return task_paused_tag in answer

    async def _query_custom(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
        """Custom user input logic."""
        # Complete the system prompt with required parameters
        completed_prompt = self._system_prompt.complete(
            task_paused_tag=task_paused_tag,
            task_completed_tag=task_completed_tag
        )
        messages = messages.add_system_prompt(completed_prompt)
        current_output = "No output"
        user_question = ""

        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

            clean_message, thinking_artifact_ref = self._process_client_response(
                response, notes
            )
            answer = clean_message

            # Log internal thinking step
            if notes is not None and step_idx > 0:
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[User Input Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            # Handle empty responses
            if answer.strip() == "":
                break

            # Extract question from the response
            user_question = get_first_text_between_tags(answer, self._output_tag, "```")

            if user_question:
                user_question = user_question.strip()
                current_output = f"Question for user: {user_question}\n\n"

                # Add question to notes for visibility
                if notes is not None:
                    model_name = getattr(self._client, "model", None)
                    note = Note(
                        message=f"User question:\n{user_question}",
                        artefact_id=None,
                        agent_name=self.get_name(),
                        model_name=model_name,
                    )
                    notes.append(note)

                # Return with pause tag to indicate waiting for user input
                if task_paused_tag not in answer:
                    answer = f"{answer}\n\n{task_paused_tag}"
                return f"{current_output}{answer}"

            # Check if agent is providing final output
            if task_completed_tag in answer:
                return answer

            # Check if agent is paused
            if self.is_paused(answer):
                return answer

            # Continue the conversation
            messages = messages.add_user_utterance(
                f"Your response: {answer}\n\n"
                f"Please provide a user question using the ```question format, or if the task is complete, use {task_completed_tag}.\n"
                f"If you need to pause for user input, use {task_paused_tag}."
            )

        return f"Could not generate a suitable user question. {task_completed_tag}"