import logging
import re
from typing import List, Tuple, Optional

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import CustomAgent, BaseAgent
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.agents.prompts import orchestrator_prompt_template
from yaaaf.components.extractors.goal_extractor import GoalExtractor
from yaaaf.components.extractors.summary_extractor import SummaryExtractor
from yaaaf.components.extractors.status_extractor import StatusExtractor
from yaaaf.components.decorators import handle_exceptions
from yaaaf.server.config import get_config

_logger = logging.getLogger(__name__)


class OrchestratorAgent(CustomAgent):
    _completing_tags: List[str] = [task_completed_tag, task_paused_tag]
    _agents_map: {str: BaseAgent} = {}
    _stop_sequences = []
    _max_steps = 10
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        super().__init__(client)
        self._agents_map = {
            key: agent(client) for key, agent in self._agents_map.items()
        }
        self._goal_extractor = GoalExtractor(client)
        self._summary_extractor = SummaryExtractor(client)
        self._status_extractor = StatusExtractor(client)
        self._current_todo_artifact_id: Optional[str] = None
        self._needs_replanning: bool = False
        self._current_stream_id: Optional[str] = None

    async def _query_custom(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        """Custom orchestrator logic."""
        return await self._orchestrate_query(messages, notes)
    
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None, stream_id: Optional[str] = None
    ) -> str:
        """Override query to accept stream_id for orchestrator."""
        return await self._orchestrate_query(messages, notes, stream_id)
    
    @handle_exceptions
    async def _orchestrate_query(
        self,
        messages: Messages,
        notes: Optional[List[Note]] = None,
        stream_id: Optional[str] = None,
    ) -> str:
        # Reset all agent budgets at the start of each query
        self._reset_all_agent_budgets()
        self._current_todo_artifact_id = None  # Reset todo tracking
        self._needs_replanning = False  # Reset replanning state
        self._current_stream_id = stream_id  # Store stream ID for status updates
        messages = messages.apply(self.simplify_agents_tags)

        # Extract goal once at the beginning
        goal = await self._goal_extractor.extract(messages)

        # Update status with extracted goal
        if stream_id:
            from yaaaf.server.accessories import update_stream_status

            update_stream_status(stream_id, goal=goal, current_agent="orchestrator")

        answer: str = ""
        for step_index in range(self._max_steps):
            # Update system prompt with current budget information at each step
            messages = messages.set_system_prompt(self._get_system_prompt(goal))
            response = await self._client.predict(
                messages, stop_sequences=self._stop_sequences
            )

            # Process response to create thinking artifacts
            clean_message, thinking_artifact_ref = self._process_client_response(
                response, notes
            )

            answer = self.simplify_agents_tags(clean_message)
            if thinking_artifact_ref:
                answer = f"{thinking_artifact_ref} {answer}"
            agent_to_call, instruction = self.map_answer_to_agent(answer)
            extracted_agent_name = Note.extract_agent_name_from_tags(answer)
            agent_name = extracted_agent_name or (
                agent_to_call.get_name() if agent_to_call else self.get_name()
            )

            if notes is not None:
                artefacts = get_artefacts_from_utterance_content(answer)
                model_name = getattr(self._client, "model", None)

                note = Note(
                    message=Note.clean_agent_tags(answer),
                    artefact_id=artefacts[0].id if artefacts else None,
                    agent_name=agent_name,
                    model_name=model_name,
                )
                note.internal = False
                notes.append(note)

            if agent_to_call is None and (
                self.is_complete(answer) or answer.strip() == ""
            ):
                # Update todo status when task is completed
                if self.is_complete(answer):
                    await self._mark_tasks_as_completed(answer)
                    config = get_config()
                    _logger.info(
                        f"Task completed - generate_summary setting: {config.generate_summary}"
                    )
                    if config.generate_summary:
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
                    # Update status before calling agent
                    if self._current_stream_id:
                        from yaaaf.server.accessories import update_stream_status

                        update_stream_status(
                            self._current_stream_id,
                            current_agent=agent_to_call.get_name(),
                        )

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

                    # Update status back to orchestrator after agent completes
                    if self._current_stream_id:
                        update_stream_status(
                            self._current_stream_id, current_agent="orchestrator"
                        )

                if notes is not None:
                    artefacts = get_artefacts_from_utterance_content(answer)
                    extracted_agent_name = Note.extract_agent_name_from_tags(answer)
                    final_agent_name = extracted_agent_name or agent_name

                    # Check if this is a todo agent response and store the artifact ID
                    if (
                        agent_to_call
                        and agent_to_call.get_name() == "todoagent"
                        and artefacts
                    ):
                        for artifact in artefacts:
                            if artifact.type == Artefact.Types.TODO_LIST:
                                self._current_todo_artifact_id = artifact.id
                                self._needs_replanning = False  # Reset replanning flag after new plan created
                                _logger.info(f"Stored todo artifact ID: {artifact.id}")
                                break

                    # Update todo status if we have a todo list and this isn't the todo agent
                    if (
                        self._current_todo_artifact_id
                        and agent_to_call
                        and agent_to_call.get_name() != "todoagent"
                    ):
                        _logger.info(
                            f"Calling status extractor for agent {final_agent_name} with response: {answer[:200]}..."
                        )
                        (
                            updated_artifact_id,
                            needs_replanning,
                        ) = await self._status_extractor.extract_and_update_status(
                            answer, final_agent_name, self._current_todo_artifact_id
                        )
                        _logger.info(
                            f"Status extractor returned: updated_id={updated_artifact_id}, needs_replanning={needs_replanning}"
                        )

                        if needs_replanning:
                            # Restore todo agent budget and mark for replanning
                            self._restore_todo_agent_budget()
                            self._needs_replanning = True
                            self._current_todo_artifact_id = (
                                None  # Reset to trigger new planning
                            )
                            _logger.info(
                                "Plan change detected - todo agent budget restored for replanning"
                            )
                        elif updated_artifact_id != self._current_todo_artifact_id:
                            self._current_todo_artifact_id = updated_artifact_id
                            _logger.info(
                                f"Updated todo artifact ID: {updated_artifact_id}"
                            )

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
            config = get_config()
            _logger.info(
                f"Max steps reached - generate_summary setting: {config.generate_summary}"
            )
            if config.generate_summary:
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

    async def _mark_tasks_as_completed(self, answer: str) -> None:
        """Mark tasks as completed in the todo list when the orchestrator finishes."""
        if self._current_todo_artifact_id:
            _logger.info(
                f"Task completed - calling status extractor with response: {answer[:200]}..."
            )
            (
                updated_artifact_id,
                needs_replanning,
            ) = await self._status_extractor.extract_and_update_status(
                answer, self.get_name(), self._current_todo_artifact_id
            )
            _logger.info(
                f"Status extractor returned: updated_id={updated_artifact_id}, needs_replanning={needs_replanning}"
            )
            if updated_artifact_id != self._current_todo_artifact_id:
                self._current_todo_artifact_id = updated_artifact_id
                _logger.info(f"Updated todo artifact ID: {updated_artifact_id}")

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

    def _restore_todo_agent_budget(self) -> None:
        """Restore todo agent budget to allow replanning."""
        for agent in self._agents_map.values():
            if agent.get_name() == "TodoAgent":
                agent.reset_budget()
                _logger.info("Restored TodoAgent budget for replanning")
                break

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
            if hasattr(agent, "get_status_info"):
                status = agent.get_status_info()
                if status.strip():
                    status_entries.append(f"• {agent.get_name()}: {status}")

        if not status_entries:
            return "No special conditions reported by agents."

        return "\n".join(status_entries)

    def _get_task_progress_section(self) -> str:
        """Generate the task progress section for the orchestrator prompt."""
        # If replanning is needed, show replanning state
        if self._needs_replanning:
            return """
== CURRENT TASK PROGRESS ==
**REPLANNING REQUIRED**: New information detected that requires updating the plan

### Current Status
- [🔄] **Creating new todo list** ←─ CURRENT STEP

### Step Context
Currently investigating: Plan revision based on new discoveries
Previous plan needs updating due to new information from sub-agent response.
"""

        if not self._current_todo_artifact_id:
            return ""

        step_info = self._status_extractor.get_current_step_info(
            self._current_todo_artifact_id
        )

        if not step_info:
            return ""

        current_step = step_info.get("current_step_index", 0)
        total_steps = step_info.get("total_steps", 0)
        current_desc = step_info.get("current_step_description", "")
        markdown_todo = step_info.get("markdown_todo_list", "")

        if not markdown_todo:
            return ""

        return f"""
== CURRENT TASK PROGRESS ==
**Step {current_step} of {total_steps}**: {current_desc}

### Todo List
{markdown_todo}

### Step Context
Currently investigating: {current_desc}
"""

    def simplify_agents_tags(self, answer: str) -> str:
        available_agents = self._get_available_agents()
        for _, agent in available_agents.items():
            opening_tag = agent.get_opening_tag().replace(">", ".*?>")
            # This is to avoid confusing the frontend
            answer = re.sub(
                rf"{opening_tag}", agent.get_opening_tag(), answer, flags=re.DOTALL
            )

        return answer

    def map_answer_to_agent(self, answer: str) -> Tuple[BaseAgent | None, str]:
        available_agents = self._get_available_agents()
        for _, agent in available_agents.items():
            opening_tag = agent.get_opening_tag().replace(">", ".*?>")
            matches = re.findall(
                rf"{opening_tag}(.+)", answer, re.DOTALL | re.MULTILINE
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

        # Generate task progress section
        task_progress_section = self._get_task_progress_section()

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
            task_progress_section=task_progress_section,
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

        # Truncate all cells to 200 characters max
        for col in df_clean.columns:
            df_clean[col] = (
                df_clean[col]
                .astype(str)
                .apply(lambda x: x[:200] + "..." if len(x) > 200 else x)
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

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Orchestrates multiple specialized agents to complete complex tasks"
