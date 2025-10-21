import logging
import re
from typing import Optional, Dict, Any
import pandas as pd

from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages
from yaaaf.components.agents.prompts import (
    status_evaluation_prompt_template,
    plan_change_evaluation_prompt_template,
)
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)


class StatusExtractor:
    def __init__(self, client: BaseClient):
        self._client = client
        self._storage = ArtefactStorage()

    @handle_exceptions
    async def extract_and_update_status(
        self,
        agent_response: str,
        agent_name: str,
        todo_artifact_id: Optional[str] = None,
    ) -> tuple[Optional[str], bool]:
        """
        Extract completion status from agent response and update todo list artifact.

        Args:
            agent_response: The response from a sub-agent
            agent_name: Name of the agent that provided the response
            todo_artifact_id: ID of the todo list artifact to update

        Returns:
            Tuple of (updated_todo_artifact_id, needs_replanning)
        """
        if not todo_artifact_id:
            return None, False

        try:
            # Retrieve the existing todo list artifact
            todo_artifact = self._storage.retrieve_from_id(todo_artifact_id)
            if not todo_artifact or todo_artifact.type != Artefact.Types.TODO_LIST:
                _logger.warning(
                    f"Todo artifact {todo_artifact_id} not found or wrong type"
                )
                return None, False

            df = todo_artifact.data.copy()

            # Skip plan change evaluation for now - just update status
            # TODO: Re-enable plan change evaluation with better prompts
            needs_replanning = False
            
            # Use LLM to evaluate step completion for tasks matching this agent
            updated = await self._evaluate_and_update_status(
                df, agent_name, agent_response
            )

            if updated:
                # Update existing artifact with same ID
                updated_artifact = Artefact(
                    type=Artefact.Types.TODO_LIST,
                    data=df,
                    description=f"Updated todo list with LLM-evaluated status from {agent_name}",
                    code=None,
                    id=todo_artifact_id,  # Reuse same ID
                )

                self._storage.store_artefact(todo_artifact_id, updated_artifact)
                _logger.info(
                    f"[STATUS_EXTRACTOR] Updated todo list artifact {todo_artifact_id} with new status from {agent_name}"
                )
                _logger.info(f"[STATUS_EXTRACTOR] Updated DataFrame:\n{df[['Task', 'Status', 'Agent/Tool']].to_string()}")
                return todo_artifact_id, False
            else:
                _logger.info(f"[STATUS_EXTRACTOR] No updates made to todo list for agent {agent_name}")

        except Exception as e:
            _logger.error(f"Failed to update todo status: {e}")

        return todo_artifact_id, False

    async def _evaluate_and_update_status(
        self,
        df: pd.DataFrame,
        agent_name: str,
        agent_response: str,
    ) -> bool:
        """
        Use LLM to evaluate step completion and update todo list status.

        Returns True if any updates were made, False otherwise.
        """
        updated = False

        # Find tasks that match this agent and are not already completed
        if "Agent/Tool" in df.columns and "Task" in df.columns:
            _logger.info(f"[STATUS_EXTRACTOR] Looking for tasks matching agent: {agent_name}")
            _logger.info(f"[STATUS_EXTRACTOR] Agent/Tool column values: {df['Agent/Tool'].tolist()}")
            
            agent_mask = df["Agent/Tool"].str.contains(agent_name, case=False, na=False)
            incomplete_mask = df["Status"] != "completed"
            tasks_to_evaluate = df[agent_mask & incomplete_mask]
            
            _logger.info(f"[STATUS_EXTRACTOR] Found {len(tasks_to_evaluate)} tasks to evaluate for agent {agent_name}")

            for idx, row in tasks_to_evaluate.iterrows():
                task_description = row["Task"]
                current_status = row["Status"]

                # Use LLM to evaluate this specific step
                try:
                    evaluation = await self._llm_evaluate_step_completion(
                        task_description, agent_response, agent_name
                    )

                    # Update status based on LLM evaluation
                    if evaluation != current_status:
                        df.loc[idx, "Status"] = evaluation
                        updated = True
                        _logger.info(
                            f"[STATUS_EXTRACTOR] LLM updated step '{task_description}' from '{current_status}' to '{evaluation}' for agent {agent_name}"
                        )
                    else:
                        _logger.info(
                            f"[STATUS_EXTRACTOR] LLM evaluation kept status as '{current_status}' for task '{task_description[:50]}...'"
                        )

                except Exception as e:
                    _logger.warning(
                        f"LLM evaluation failed for step '{task_description}': {e}"
                    )
                    # Fallback to simple heuristics
                    fallback_status = self._fallback_status_evaluation(
                        agent_response, current_status
                    )
                    if fallback_status != current_status:
                        df.loc[idx, "Status"] = fallback_status
                        updated = True

        return updated

    async def _evaluate_plan_changes(
        self,
        df: pd.DataFrame,
        agent_name: str,
        agent_response: str,
    ) -> bool:
        """
        Evaluate if the agent response indicates the plan needs to change.

        Returns True if replanning is needed, False otherwise.
        """
        try:
            # Generate markdown representation of current todo list
            original_todo_markdown = df.to_markdown(index=False)

            # Use LLM to evaluate if plan changes are needed
            messages = Messages().add_system_prompt(
                plan_change_evaluation_prompt_template.complete(
                    original_todo_list=original_todo_markdown,
                    agent_response=agent_response,
                    agent_name=agent_name,
                )
            )

            response = await self._client.predict(messages, stop_sequences=[])
            evaluation = response.message.strip().lower()
            
            _logger.info(f"[STATUS_EXTRACTOR] Plan change evaluation for {agent_name}: '{evaluation}' (raw: '{response.message}')")

            # Check if plan change is needed
            if evaluation == "yes":
                _logger.info(
                    f"[STATUS_EXTRACTOR] LLM determined plan change needed based on {agent_name} response"
                )
                return True
            elif evaluation == "no":
                _logger.info(f"[STATUS_EXTRACTOR] No plan change needed for {agent_name}")
                return False
            else:
                _logger.warning(
                    f"[STATUS_EXTRACTOR] Invalid plan change evaluation response: '{evaluation}', defaulting to no change"
                )
                return False

        except Exception as e:
            _logger.error(f"Plan change evaluation failed: {e}")
            return False

    async def _llm_evaluate_step_completion(
        self,
        step_description: str,
        agent_response: str,
        agent_name: str,
    ) -> str:
        """
        Use LLM to evaluate if a specific step has been completed.

        Returns: "completed", "in_progress", or "pending"
        """
        messages = Messages().add_system_prompt(
            status_evaluation_prompt_template.complete(
                current_step_description=step_description,
                agent_response=agent_response,
                agent_name=agent_name,
            )
        )

        response = await self._client.predict(messages, stop_sequences=[])
        evaluation = response.message.strip().lower()

        # Validate the response
        valid_statuses = ["completed", "in_progress", "pending"]
        if evaluation in valid_statuses:
            return evaluation
        else:
            _logger.warning(
                f"Invalid LLM evaluation response: '{evaluation}', defaulting to 'in_progress'"
            )
            return "in_progress"

    def _fallback_status_evaluation(self, response: str, current_status: str) -> str:
        """Fallback status evaluation using simple heuristics."""
        if (
            task_completed_tag in response
            or task_paused_tag in response
            or "task is complete" in response.lower()
            or "completed successfully" in response.lower()
        ):
            return "completed"
        elif self._has_meaningful_content(response):
            return "in_progress"
        else:
            return current_status

    def _has_meaningful_content(self, response: str) -> bool:
        """Check if response has meaningful content indicating work in progress."""
        # Remove common tags and whitespace
        clean_response = re.sub(r"<[^>]+>", "", response).strip()
        return len(clean_response) > 10  # Has substantial content

    def get_current_step_info(self, todo_artifact_id: Optional[str]) -> Dict[str, Any]:
        """
        Extract current step information from todo list artifact.

        Returns:
            Dictionary with current step context for orchestrator prompt
        """
        if not todo_artifact_id:
            return {}

        try:
            todo_artifact = self._storage.retrieve_from_id(todo_artifact_id)
            if not todo_artifact or todo_artifact.type != Artefact.Types.TODO_LIST:
                return {}

            df = todo_artifact.data

            # Find current step (first in_progress, or first pending if none in progress)
            current_step_idx = None
            current_step_desc = ""

            if "Status" in df.columns and "Task" in df.columns:
                # Look for in_progress first
                in_progress_mask = df["Status"] == "in_progress"
                if in_progress_mask.any():
                    current_step_idx = df[in_progress_mask].index[0]
                else:
                    # Look for first pending
                    pending_mask = df["Status"] == "pending"
                    if pending_mask.any():
                        current_step_idx = df[pending_mask].index[0]

                if current_step_idx is not None:
                    current_step_desc = df.loc[current_step_idx, "Task"]

            # Generate markdown todo list
            markdown_todo = self._generate_markdown_todo_list(df, current_step_idx)

            return {
                "current_step_index": current_step_idx + 1
                if current_step_idx is not None
                else 0,
                "total_steps": len(df),
                "current_step_description": current_step_desc,
                "markdown_todo_list": markdown_todo,
                "artifact_id": todo_artifact_id,
            }

        except Exception as e:
            _logger.error(f"Failed to get current step info: {e}")
            return {}

    def _generate_markdown_todo_list(
        self, df: pd.DataFrame, current_step_idx: Optional[int]
    ) -> str:
        """Generate markdown todo list with checkboxes and current step highlighting."""
        if df.empty:
            return ""

        lines = []
        for idx, row in df.iterrows():
            task = row.get("Task", "")
            status = row.get("Status", "pending")

            # If this is the current step, override status display
            if idx == current_step_idx:
                if status == "completed":
                    checkbox = "[x]"
                else:
                    checkbox = "[🔄]"  # Show as in progress for current step
                lines.append(f"- {checkbox} **{task}** ←─ CURRENT STEP")
            else:
                # Choose checkbox based on status for non-current steps
                if status == "completed":
                    checkbox = "[x]"
                elif status == "in_progress":
                    checkbox = "[🔄]"
                else:
                    checkbox = "[ ]"
                lines.append(f"- {checkbox} {task}")

        return "\n".join(lines)

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this extractor does."""
        return "Extracts and updates task completion status from agent responses"
