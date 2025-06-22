import logging
import re
from typing import List, Tuple, Optional

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.agents.prompts import orchestrator_prompt_template
from yaaaf.components.extractors.goal_extractor import GoalExtractor
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag, task_paused_tag]
    _agents_map: {str: BaseAgent} = {}
    _stop_sequences = []
    _max_steps = 10
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client
        self._agents_map = {
            key: agent(client) for key, agent in self._agents_map.items()
        }
        self._goal_extractor = GoalExtractor(client)

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        messages = messages.add_system_prompt(
            self._get_system_prompt(await self._goal_extractor.extract(messages))
        )

        answer: str = ""
        for step_index in range(self._max_steps):
            answer = await self._client.predict(
                messages, stop_sequences=self._stop_sequences
            )
            agent_to_call, instruction = self.map_answer_to_agent(answer)
            extracted_agent_name = Note.extract_agent_name_from_tags(answer)
            agent_name = extracted_agent_name or (
                agent_to_call.get_name() if agent_to_call else self.get_name()
            )

            if notes is not None:
                artefacts = get_artefacts_from_utterance_content(answer)
                # Get model name from client if available
                model_name = getattr(self._client, "model", None)
                note = Note(
                    message=Note.clean_agent_tags(answer),
                    artefact_id=artefacts[0].id if artefacts else None,
                    agent_name=agent_name,
                    model_name=model_name,
                )
                notes.append(note)

            if self.is_complete(answer) or answer.strip() == "":
                break
            if agent_to_call is not None:
                if notes is not None:
                    messages = messages.add_assistant_utterance(
                        f"Calling {agent_name} with instruction:\n\n{instruction}\n\n"
                    )
                answer = await agent_to_call.query(
                    Messages().add_user_utterance(instruction),
                    notes=notes,
                )
                answer = self._make_output_visible(answer)

                if notes is not None:
                    artefacts = get_artefacts_from_utterance_content(answer)
                    extracted_agent_name = Note.extract_agent_name_from_tags(answer)
                    final_agent_name = extracted_agent_name or agent_name

                    # Get model name from the agent's client if available
                    agent_model_name = (
                        getattr(agent_to_call._client, "model", None)
                        if agent_to_call
                        else None
                    )
                    note = Note(
                        message=Note.clean_agent_tags(answer),
                        artefact_id=artefacts[0].id if artefacts else None,
                        agent_name=final_agent_name,
                        model_name=agent_model_name,
                    )
                    notes.append(note)

                messages = messages.add_user_utterance(
                    f"The answer from the agent is:\n\n{answer}\n\nWhen you are 100% sure about the answer and the task is done, write the tag {self._completing_tags[0]}."
                )
            else:
                messages = messages.add_assistant_utterance(answer)
                messages = messages.add_user_utterance(
                    "You didn't call any agent. Is the answer finished or did you miss outputting the tags? Reminder: use the relevant html tags to call the agents.\n\n"
                )
        if not self.is_complete(answer) and step_index == self._max_steps - 1:
            answer += f"\nThe Orchestrator agent has finished its maximum number of steps. {task_completed_tag}"
            if notes is not None:
                model_name = getattr(self._client, "model", None)
                notes.append(
                    Note(
                        message=f"The Orchestrator agent has finished its maximum number of steps. {task_completed_tag}",
                        agent_name=self.get_name(),
                        model_name=model_name,
                    )
                )
        return answer

    def is_paused(self, answer: str) -> bool:
        """Check if the task is paused and waiting for user input."""
        return task_paused_tag in answer

    def subscribe_agent(self, agent: BaseAgent):
        if agent.get_opening_tag() in self._agents_map:
            raise ValueError(
                f"Agent with tag {agent.get_opening_tag()} already exists."
            )
        self._agents_map[agent.get_opening_tag()] = agent
        self._stop_sequences.append(agent.get_closing_tag())

        _logger.info(
            f"Registered agent: {agent.get_name()} (tag: {agent.get_opening_tag()})"
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

    def _get_system_prompt(self, goal: str) -> str:
        # Get training cutoff information from the client if available
        training_cutoff_info = ""
        if hasattr(self._client, "get_training_cutoff_date"):
            cutoff_date = self._client.get_training_cutoff_date()
            if cutoff_date:
                training_cutoff_info = f"Your training date cutoff is {cutoff_date}. You have been trained to know only information before that date."

        return orchestrator_prompt_template.complete(
            training_cutoff_info=training_cutoff_info,
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
            goal=goal,
        )

    def _sanitize_dataframe_for_markdown(self, df) -> str:
        """Sanitize dataframe data to prevent markdown table breakage."""
        # Create a copy to avoid modifying the original
        df_clean = df.copy()

        # Apply sanitization to all string columns
        for col in df_clean.columns:
            if df_clean[col].dtype == "object":  # String columns
                df_clean[col] = (
                    df_clean[col]
                    .astype(str)
                    .apply(
                        lambda x: (
                            x.replace("|", "\\|")  # Escape pipe characters
                            .replace("\n", " ")  # Replace newlines with spaces
                            .replace("\r", " ")  # Replace carriage returns
                            .replace("\t", " ")  # Replace tabs with spaces
                            .strip()  # Remove leading/trailing whitespace
                        )
                    )
                )

        return df_clean.to_markdown(index=False)

    def _make_output_visible(self, answer: str) -> str:
        """Make the output visible by printing or visualising the content of artefacts"""
        if "<artefact type='image'>" in answer:
            image_artefact: Artefact = get_artefacts_from_utterance_content(answer)[0]
            answer = f"<imageoutput>{image_artefact.id}</imageoutput>" + "\n" + answer
        if "<artefact type='paragraphs-table'>" in answer:
            artefact: Artefact = get_artefacts_from_utterance_content(answer)[0]
            answer = (
                f"<markdown>{self._sanitize_dataframe_for_markdown(artefact.data)}</markdown>"
                + answer
            )
        if "<artefact type='called-tools-table'>" in answer:
            artefact: Artefact = get_artefacts_from_utterance_content(answer)[0]
            answer = (
                f"<markdown>{self._sanitize_dataframe_for_markdown(artefact.data)}</markdown>"
                + answer
            )
        return answer
