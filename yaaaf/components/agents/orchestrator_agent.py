import logging
import re
from typing import List, Tuple, Optional

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.agents.task_completed_agent import TaskCompletedAgent
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note, Tool
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
        
        # Add TaskCompletedAgent by default
        task_completed_agent = TaskCompletedAgent(client)
        self.subscribe_agent(task_completed_agent)

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
            
            # Get available tools for agents with budget > 0
            tools = self._get_tools()
            
            response = await self._client.predict(
                messages, stop_sequences=self._stop_sequences, tools=tools
            )
            
            # Handle tool calls vs regular messages
            if response.tool_calls:
                # Process tool call
                tool_call = response.tool_calls[0]  # Take the first tool call
                agent_name = tool_call.function["name"]
                
                # Find the agent by name
                agent_to_call = None
                for agent in self._agents_map.values():
                    if agent.get_name() == agent_name:
                        agent_to_call = agent
                        break
                
                if agent_to_call is None:
                    answer = f"Unknown agent: {agent_name}"
                    _logger.error(f"Tool call requested unknown agent: {agent_name}")
                elif agent_to_call.get_budget() <= 0:
                    answer = f"Agent {agent_name} has exhausted its budget and cannot be called again."
                    _logger.warning(f"Agent {agent_name} has exhausted its budget")
                else:
                    # Consume budget before calling agent
                    agent_to_call.consume_budget()
                    _logger.info(f"Agent {agent_name} called via tool, remaining budget: {agent_to_call.get_budget()}")
                    
                    # Extract instruction and artefact_id from tool call
                    tool_args = tool_call.function.get("arguments", {})
                    instruction = tool_args.get("instruction", "")
                    artefact_id = tool_args.get("artefact_id", None)
                    
                    # Build the XML tag message for visibility
                    xml_tag_message = f"{agent_to_call.get_opening_tag()}{instruction}"
                    if artefact_id:
                        xml_tag_message += f" <artefact>{artefact_id}</artefact>"
                    xml_tag_message += f"{agent_to_call.get_closing_tag()}"
                    
                    # Add the XML tag message to the conversation
                    messages = messages.add_assistant_utterance(xml_tag_message)
                    
                    # Add note for the agent call
                    if notes is not None:
                        model_name = getattr(self._client, "model", None)
                        call_note = Note(
                            message=xml_tag_message,
                            artefact_id=artefact_id,
                            agent_name=self.get_name(),
                            model_name=model_name,
                        )
                        call_note.internal = False
                        notes.append(call_note)

                    # Build the clean message for the agent (without XML tags)
                    agent_message = instruction
                    if artefact_id:
                        agent_message += f" <artefact>{artefact_id}</artefact>"
                    
                    # Call the agent
                    agent_response = await agent_to_call.query(
                        Messages().add_user_utterance(agent_message),
                        notes=notes,
                    )
                    
                    # Wrap the agent response in tags
                    answer = f"{agent_to_call.get_opening_tag()}{agent_response}{agent_to_call.get_closing_tag()}"
                    answer = self._make_output_visible(answer)
            else:
                # Handle regular message (no tool call)
                answer = response.message
                
            # Add note for this step
            if notes is not None:
                artefacts = get_artefacts_from_utterance_content(answer)
                model_name = getattr(self._client, "model", None)
                
                # Determine agent name for the note
                if response.tool_calls:
                    agent_name = response.tool_calls[0].function["name"]
                else:
                    agent_name = self.get_name()

                note = Note(
                    message=self._remove_and_extract_completion_tag(Note.clean_agent_tags(answer)),
                    artefact_id=artefacts[0].id if artefacts else None,
                    agent_name=agent_name,
                    model_name=model_name,
                )
                note.internal = False
                notes.append(note)
            
            # Add the response to messages for next iteration
            messages = messages.add_assistant_utterance(answer)

            # Check if we should stop
            if self.is_complete(answer) or answer.strip() == "":
                # Generate summary artifact when task is completed
                if self.is_complete(answer):
                    answer = await self._generate_and_add_summary(answer, notes)
                break
        # Handle max steps reached
        if not self.is_complete(answer):
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

    def _get_tools(self) -> List[Tool]:
        """Get tools for all agents that have budget remaining."""
        available_agents = self._get_available_agents()
        tools = []
        for agent in available_agents.values():
            tools.append(agent.get_tool())
        return tools

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
                    + f"{agent.get_name()}: {agent.get_description().strip()}"
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
