"""
Streamlined orchestrator agent using modular utilities.
This is a cleaner, more maintainable version of the orchestrator.
"""
import logging
from typing import List, Optional

from yaaaf.components.agents.base_agent import CustomAgent, BaseAgent
from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.extractors.goal_extractor import GoalExtractor
from yaaaf.components.extractors.summary_extractor import SummaryExtractor
from yaaaf.components.extractors.status_extractor import StatusExtractor
from yaaaf.components.decorators import handle_exceptions
from yaaaf.components.orchestrator.agent_manager import AgentManager
from yaaaf.components.orchestrator.status_tracker import StatusTracker
from yaaaf.components.orchestrator.response_processor import ResponseProcessor
from yaaaf.components.orchestrator.prompt_builder import PromptBuilder
from yaaaf.server.config import get_config

_logger = logging.getLogger(__name__)


class OrchestratorAgent(CustomAgent):
    """Streamlined orchestrator using modular utilities."""
    
    _completing_tags: List[str] = [task_completed_tag, task_paused_tag]
    
    def __init__(self, client: BaseClient):
        super().__init__(client)
        
        # Core utilities
        self._agent_manager = AgentManager()
        self._goal_extractor = GoalExtractor(client)
        self._summary_extractor = SummaryExtractor(client)
        self._status_extractor = StatusExtractor(client)
        
        # Tracking and processing utilities
        self._status_tracker = StatusTracker(self._status_extractor)
        self._response_processor = ResponseProcessor()
        self._prompt_builder = PromptBuilder(self._agent_manager, self._status_tracker, client)
    
    def subscribe_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the orchestrator."""
        self._agent_manager.register_agent(agent)
    
    @handle_exceptions
    async def _query_custom(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
        """Custom orchestrator logic."""
        return await self._orchestrate_query(messages, notes)
    
    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[Note]] = None, stream_id: Optional[str] = None) -> str:
        """Override query to accept stream_id for orchestrator."""
        return await self._orchestrate_query(messages, notes, stream_id)
    
    async def _orchestrate_query(
        self,
        messages: Messages,
        notes: Optional[List[Note]] = None,
        stream_id: Optional[str] = None,
    ) -> str:
        """Main orchestration logic - streamlined version."""
        
        # Initialize for new query
        self._agent_manager.reset_all_budgets()
        self._status_tracker.reset_for_new_query(stream_id)
        messages = messages.apply(self._agent_manager.simplify_agent_tags)
        
        # Extract goal
        goal = await self._extract_goal(messages)
        self._status_tracker.update_stream_status(goal=goal, current_agent="orchestrator")
        
        # Auto-call todo agent first if no todo artifact exists
        if not self._status_tracker.has_todo_artifact:
            await self._auto_call_todo_agent(messages, notes, goal)
        
        # Main orchestration loop
        answer = ""
        for step_index in range(self._max_steps):
            # Build dynamic system prompt
            system_prompt = self._prompt_builder.build_system_prompt(goal)
            messages = messages.set_system_prompt(system_prompt)
            
            # Get response from LLM
            response = await self._client.predict(
                messages, stop_sequences=self._agent_manager.get_stop_sequences()
            )
            
            # Process response
            clean_message, thinking_ref = self._response_processor.process_client_response(
                response, notes, self.get_name()
            )
            
            answer = self._agent_manager.simplify_agent_tags(clean_message)
            if thinking_ref:
                answer = f"{thinking_ref} {answer}"
            
            # Check for completion
            if self._should_complete(answer):
                # Create orchestrator note for final response
                if notes is not None:
                    self._response_processor.create_orchestrator_note(
                        answer, self.get_name(), getattr(self._client, "model", None), notes
                    )
                if self.is_complete(answer):
                    await self._handle_completion(answer, notes)
                    answer = await self._maybe_add_summary(answer, notes)
                break
            
            # Route to agent and execute
            answer, messages = await self._execute_agent_if_needed(answer, messages, notes)
            if self.is_complete(answer):
                break
        
        # Handle max steps reached
        if not self.is_complete(answer) and step_index == self._max_steps - 1:
            answer = await self._handle_max_steps_reached(answer, notes)
        
        return answer
    
    async def _auto_call_todo_agent(self, messages: Messages, notes: Optional[List[Note]], goal: str) -> None:
        """Automatically call todo agent first to create initial task plan."""
        # Find todo agent
        todo_agent = None
        for agent in self._agent_manager._agents.values():
            if agent.get_name() == "todoagent":
                todo_agent = agent
                break
        
        if todo_agent and todo_agent.get_budget() > 0:
            _logger.info("Auto-calling todo agent to create initial plan")
            
            # Create the orchestrator's decision to call todo agent
            orchestrator_decision = f"<todoagent>Create a structured todo list for: {goal}</todoagent>"
            
            # Create note showing orchestrator's decision to call todo agent
            if notes is not None:
                self._response_processor.create_orchestrator_note(
                    orchestrator_decision, todo_agent.get_name(), getattr(self._client, "model", None), notes
                )
            
            # Create instruction for todo agent based on goal
            instruction = f"Create a structured todo list for: {goal}"
            
            # Execute todo agent
            response = await self._execute_agent(todo_agent, instruction, messages, notes)
            _logger.info(f"Todo agent auto-call completed: {response[:100]}...")
    
    async def _extract_goal(self, messages: Messages) -> str:
        """Extract goal with error handling."""
        try:
            return await self._goal_extractor.extract(messages)
        except Exception as e:
            _logger.warning(f"Goal extraction failed, using fallback: {e}")
            raise  # Let @handle_exceptions handle it
    
    def _should_complete(self, answer: str) -> bool:
        """Check if orchestrator should complete."""
        return (
            self._agent_manager.route_to_agent(answer)[0] is None and
            (self.is_complete(answer) or answer.strip() == "")
        )
    
    async def _execute_agent_if_needed(self, answer: str, messages: Messages, notes: Optional[List[Note]]) -> tuple[str, Messages]:
        """Execute agent if routing is needed."""
        agent_to_call, instruction = self._agent_manager.route_to_agent(answer)
        
        if agent_to_call is None:
            # No agent to call, provide feedback
            updated_messages = messages.add_assistant_utterance(answer)
            updated_messages = updated_messages.add_user_utterance(
                "You didn't call any agent. Is the answer finished or did you miss outputting the tags? "
                "Reminder: use the relevant html tags to call the agents."
            )
            return answer, updated_messages
        
        # Create orchestrator note showing the decision to call an agent
        if notes is not None:
            self._response_processor.create_orchestrator_note(
                answer, agent_to_call.get_name(), getattr(self._client, "model", None), notes
            )
        
        # Check agent budget
        if agent_to_call.get_budget() <= 0:
            _logger.warning(f"Agent {agent_to_call.get_name()} has exhausted its budget")
            return f"Agent {agent_to_call.get_name()} has exhausted its budget and cannot be called again.", messages
        
        # Execute agent and update conversation
        agent_response = await self._execute_agent(agent_to_call, instruction, messages, notes)
        
        # Update messages with agent response and feedback for next iteration
        updated_messages = messages.add_assistant_utterance(answer)
        updated_messages = updated_messages.add_user_utterance(
            f"The answer from the agent is:\n\n{agent_response}\n\nWhen you are 100% sure about the answer and the task is done, write the tag {task_completed_tag}."
        )
        
        return agent_response, updated_messages
    
    async def _execute_agent(self, agent: BaseAgent, instruction: str, messages: Messages, notes: Optional[List[Note]]) -> str:
        """Execute a specific agent with instruction."""
        # Update status
        self._status_tracker.update_stream_status(current_agent=agent.get_name())
        
        # Consume budget and execute
        agent.consume_budget()
        _logger.info(f"Agent {agent.get_name()} called, remaining budget: {agent.get_budget()}")
        
        # Execute agent
        agent_response = await agent.query(
            Messages().add_user_utterance(instruction),
            notes=notes,
        )
        
        # Process response
        agent_response = self._response_processor.make_output_visible(agent_response)
        
        # Handle todo artifacts and status updates
        await self._handle_agent_response(agent_response, agent, notes)
        
        # Update status back to orchestrator
        self._status_tracker.update_stream_status(current_agent="orchestrator")
        
        return agent_response
    
    async def _handle_agent_response(self, response: str, agent: BaseAgent, notes: Optional[List[Note]]) -> None:
        """Handle agent response artifacts and status updates."""
        if notes is None:
            return
        
        from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
        from yaaaf.components.agents.artefacts import Artefact
        
        artefacts = get_artefacts_from_utterance_content(response)
        
        # Check for todo artifacts
        todo_artifact_id = self._response_processor.handle_todo_artifact(
            response, agent.get_name(), artefacts
        )
        if todo_artifact_id:
            self._status_tracker.set_todo_artifact(todo_artifact_id)
            _logger.info(f"[ORCHESTRATOR] Set todo artifact ID: {todo_artifact_id} for agent: {agent.get_name()}")
        else:
            _logger.info(f"[ORCHESTRATOR] No todo artifact found for agent: {agent.get_name()}, artifacts count: {len(artefacts)}")
        
        # Update task status if we have a todo list
        if self._status_tracker.has_todo_artifact and agent.get_name() != "todoagent":
            _logger.info(f"[ORCHESTRATOR] Updating task status for agent: {agent.get_name()}")
            await self._status_tracker.update_task_status(response, agent.get_name())
        else:
            _logger.info(f"[ORCHESTRATOR] NOT updating status - has_todo: {self._status_tracker.has_todo_artifact}, agent: {agent.get_name()}")
        
        # Create agent note
        agent_model_name = getattr(agent._client, "model", None) if agent else None
        self._response_processor.create_agent_note(
            response, agent.get_name(), agent_model_name, notes
        )
    
    async def _handle_completion(self, answer: str, notes: Optional[List[Note]]) -> None:
        """Handle task completion."""
        await self._status_tracker.mark_tasks_completed(answer, self.get_name())
    
    async def _maybe_add_summary(self, answer: str, notes: Optional[List[Note]]) -> str:
        """Add summary if configured."""
        config = get_config()
        _logger.info(f"Task completed - generate_summary setting: {config.generate_summary}")
        
        if config.generate_summary:
            return await self._generate_and_add_summary(answer, notes)
        return answer
    
    async def _handle_max_steps_reached(self, answer: str, notes: Optional[List[Note]]) -> str:
        """Handle when max steps are reached."""
        answer += f"\nThe Orchestrator agent has finished its maximum number of steps. {task_completed_tag}"
        
        # Generate summary if configured
        answer = await self._maybe_add_summary(answer, notes)
        
        # Add final note
        if notes is not None:
            from yaaaf.components.data_types import Note
            model_name = getattr(self._client, "model", None)
            notes.append(
                Note(
                    message=f"The Orchestrator agent has finished its maximum number of steps. {task_completed_tag}",
                    agent_name=self.get_name(),
                    model_name=model_name,
                )
            )
        
        return answer
    
    async def _generate_and_add_summary(self, answer: str, notes: Optional[List[Note]]) -> str:
        """Generate summary artifact and add it to notes."""
        if not notes:
            return answer
        
        summary_result = await self._summary_extractor.extract(notes)
        if summary_result:
            updated_answer = f"\n\n{summary_result}\n\n{task_completed_tag}"
            
            from yaaaf.components.data_types import Note
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
    
    def get_description(self) -> str:
        return "Orchestrator agent: This agent orchestrates the agents."
    
    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Orchestrates multiple specialized agents to complete complex tasks"