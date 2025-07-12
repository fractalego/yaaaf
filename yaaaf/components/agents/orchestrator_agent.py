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
from yaaaf.components.extractors.summary_extractor import SummaryExtractor
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
        self._summary_extractor = SummaryExtractor(client)

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        # Reset all agent budgets at the start of each query
        self._reset_all_agent_budgets()

        # Extract goal once at the beginning
        goal = await self._goal_extractor.extract(messages)

        answer: str = ""
        for step_index in range(self._max_steps):
            # Update system prompt with current budget information at each step
            messages = messages.set_system_prompt(self._get_system_prompt(goal))
            response = await self._client.predict(
                messages, stop_sequences=self._stop_sequences
            )
            answer = response.message
            agent_to_call, instruction = self.map_answer_to_agent(answer)
            extracted_agent_name = Note.extract_agent_name_from_tags(answer)
            agent_name = extracted_agent_name or (
                agent_to_call.get_name() if agent_to_call else self.get_name()
            )

            if notes is not None:
                artefacts = get_artefacts_from_utterance_content(answer)
                model_name = getattr(self._client, "model", None)

                note = Note(
                    message=self._remove_and_extract_completion_tag(Note.clean_agent_tags(answer)),
                    artefact_id=artefacts[0].id if artefacts else None,
                    agent_name=agent_name,
                    model_name=model_name,
                )
                note.internal = False
                notes.append(note)

            if agent_to_call is None and (
                self.is_complete(answer) or answer.strip() == ""
            ):
                # Generate summary artifact when task is completed
                if self.is_complete(answer):
                    answer = await self._generate_and_add_summary(answer, notes)
                break
            if agent_to_call is not None:
                # Check if agent has budget remaining
                if agent_to_call.get_budget() <= 0:
                    _logger.warning(
                        f"Agent {agent_to_call.get_name()} has exhausted its budget"
                    )
                    answer = f"Agent {agent_to_call.get_name()} has exhausted its budget and cannot be called again."
                else:
                    # Consume budget before calling agent
                    agent_to_call.consume_budget()
                    _logger.info(
                        f"Agent {agent_to_call.get_name()} called, remaining budget: {agent_to_call.get_budget()}"
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

                    # Add cleaned user-facing note
                    note = Note(
                        message=Note.clean_agent_tags(answer),
                        artefact_id=artefacts[0].id if artefacts else None,
                        agent_name=final_agent_name,
                        model_name=agent_model_name,
                    )
                    note.internal = False
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
            # Generate summary artifact when max steps reached
            answer = await self._generate_and_add_summary(answer, notes)
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

    def _remove_and_extract_completion_tag(self, answer: str) -> str:
        cleaned_answer = answer.replace(task_completed_tag, "").strip()
        return cleaned_answer

    async def _generate_and_add_summary(
        self, answer: str, notes: Optional[List[Note]] = None
    ) -> str:
        """Generate summary artifact and add it to notes, returning updated answer."""
        if not notes:
            return answer

        summary_result = await self._summary_extractor.extract(notes)
        if summary_result:
            updated_answer = f"\n\n{summary_result}\n\n{task_completed_tag}"
            model_name = getattr(self._client, "model", None)
            notes.append(
                Note(
                    message=updated_answer,
                    agent_name=self.get_name(),
                    model_name=model_name,
                )
            )
            return updated_answer
        return answer

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

    def _reset_all_agent_budgets(self) -> None:
        """Reset budgets for all agents at the start of a new query."""
        for agent in self._agents_map.values():
            agent.reset_budget()
        _logger.info("Reset budgets for all agents")

    def _get_available_agents(self) -> dict:
        """Get agents that still have budget remaining."""
        return {
            tag: agent
            for tag, agent in self._agents_map.items()
            if agent.get_budget() > 0
        }

    def _get_system_status(self) -> str:
        """Collect status information from all agents."""
        status_entries = []
        
        for agent in self._agents_map.values():
            if hasattr(agent, 'get_status_info'):
                status = agent.get_status_info()
                if status.strip():
                    status_entries.append(f"• {agent.get_name()}: {status}")
        
        if not status_entries:
            return "No special conditions reported by agents."
        
        return "\n".join(status_entries)

    def map_answer_to_agent(self, answer: str) -> Tuple[BaseAgent | None, str]:
        # Only consider agents that still have budget
        available_agents = self._get_available_agents()

        for tag, agent in available_agents.items():
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

        # Only include agents that still have budget
        available_agents = self._get_available_agents()

        # Generate budget information
        budget_info = "Current agent budgets (remaining calls):\n" + "\n".join(
            [
                f"• {agent.get_name()}: {agent.get_budget()} calls remaining"
                for agent in available_agents.values()
            ]
        )

        return orchestrator_prompt_template.complete(
            training_cutoff_info=training_cutoff_info,
            agents_list="\n".join(
                [
                    "* "
                    + agent.get_description().strip()
                    + f" (Budget: {agent.get_budget()} calls)\n"
                    for agent in available_agents.values()
                ]
            ),
            all_tags_list="\n".join(
                [
                    agent.get_opening_tag().strip() + agent.get_closing_tag().strip()
                    for agent in available_agents.values()
                ]
            ),
            budget_info=budget_info,
            status_info=self._get_system_status(),
            goal=goal,
            task_completed_tag=task_completed_tag,
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

    def _sanitize_and_truncate_dataframe_for_markdown(
        self, df, max_rows: int = 5
    ) -> str:
        """Sanitize dataframe and truncate to first max_rows, showing ellipsis if truncated."""
        # Create a copy to avoid modifying the original
        df_clean = df.copy()

        # Apply basic sanitization to all string columns - keep it simple to avoid encoding issues
        for col in df_clean.columns:
            if df_clean[col].dtype == "object":  # String columns
                df_clean[col] = (
                    df_clean[col]
                    .astype(str)
                    .apply(
                        lambda x: (
                            # Only do basic cleaning - let frontend handle the rest
                            x.replace("\n", " ")  # Replace newlines with spaces
                            .replace("\r", " ")  # Replace carriage returns
                            .replace("\t", " ")  # Replace tabs with spaces
                            .strip()  # Remove leading/trailing whitespace
                        )
                    )
                )

        # Check if we need to truncate
        is_truncated = len(df_clean) > max_rows
        df_display = df_clean.head(max_rows)

        # Convert to markdown - keep it simple
        markdown_table = df_display.to_markdown(index=False)

        # Add ellipsis indicator if truncated
        if is_truncated:
            total_rows = len(df_clean)
            markdown_table += f"\n\n*... ({total_rows - max_rows} more rows)*"

        return markdown_table

    def _make_output_visible(self, answer: str) -> str:
        """Make the output visible by printing or visualising the content of artefacts"""
        # Handle images
        if "<artefact type='image'>" in answer:
            image_artefact: Artefact = get_artefacts_from_utterance_content(answer)[0]
            answer = f"<imageoutput>{image_artefact.id}</imageoutput>" + "\n" + answer

        # Handle ALL table types - get all artefacts from the answer
        artefacts = get_artefacts_from_utterance_content(answer)
        for artefact in artefacts:
            # Check if this artefact has table data (DataFrame)
            if artefact.data is not None and hasattr(artefact.data, "to_markdown"):
                try:
                    # Handle todo-list artifacts differently - show full table
                    if artefact.type == Artefact.Types.TODO_LIST:
                        markdown_table = self._sanitize_dataframe_for_markdown(
                            artefact.data
                        )
                        logger_msg = f"Added full todo-list table with {len(artefact.data)} rows to output"
                    else:
                        # Regular tables - display with truncation
                        markdown_table = (
                            self._sanitize_and_truncate_dataframe_for_markdown(
                                artefact.data
                            )
                        )
                        logger_msg = (
                            f"Added table with {len(artefact.data)} rows to output"
                        )

                    # Prepend the table display to the answer
                    answer = f"<markdown>{markdown_table}</markdown>\n" + answer
                    # Debug logging
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(logger_msg)
                except Exception as e:
                    # If table processing fails, log it but don't break the flow
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to process table for display: {e}")

        return answer
