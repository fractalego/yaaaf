import logging
from typing import Optional, List, TYPE_CHECKING
from abc import ABC, abstractmethod

from yaaaf.components.data_types import Note, Messages, PromptTemplate, AgentTaxonomy, AgentArtifactSpec
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.decorators import handle_exceptions
from yaaaf.components.agents.agent_steps_config import AGENT_MAX_STEPS, DEFAULT_MAX_STEPS
from yaaaf.components.agents.artefact_utils import create_prompt_from_artefacts

if TYPE_CHECKING:
    from yaaaf.components.data_types import ClientResponse
    from yaaaf.components.client import BaseClient
    from yaaaf.components.executors import ToolExecutor

_logger = logging.getLogger(__name__)


def get_agent_name_from_class(agent_class) -> str:
    """Get agent name from class - used by both get_name() and orchestrator builder."""
    return agent_class.__name__.lower()


class BaseAgent(ABC):
    """Modern base agent with unified execution patterns.
    
    All agents inherit from this and either:
    1. Use ToolExecutor pattern (preferred for most agents)
    2. Implement custom query logic (for complex coordination agents)
    """
    
    # Class attributes with defaults
    _completing_tags: List[str] = [task_completed_tag]
    _stop_sequences: List[str] = [task_completed_tag]
    _output_tag: Optional[str] = None
    _system_prompt: Optional[PromptTemplate] = None
    _storage = ArtefactStorage()  # Singleton instance
    
    def __init__(self):
        self._budget = 2
        self._original_budget = 2
        self._artefact_extractor = None
        self._client: Optional["BaseClient"] = None
        self._executor: Optional["ToolExecutor"] = None
        
        # Get max steps from config based on agent name
        agent_name = get_agent_name_from_class(self.__class__)
        self._max_steps = AGENT_MAX_STEPS.get(agent_name, DEFAULT_MAX_STEPS)
    
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        """Execute query using ToolExecutor or custom implementation."""
        if self._executor:
            return await self._query_with_executor(messages, notes)
        else:
            return await self._query_custom(messages, notes)
    
    @handle_exceptions
    async def _query_with_executor(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        """Standard query implementation using ToolExecutor pattern."""
        if not self._client:
            raise ValueError("Agent with executor requires client")
        
        # Prepare context using executor
        context = await self._executor.prepare_context(messages, notes)
        
        # Add system prompt if available
        if self._system_prompt:
            # Try to complete prompt with artifacts if available
            completed_prompt = self._try_complete_prompt_with_artifacts(context)
            messages = messages.add_system_prompt(completed_prompt)
        
        # Multi-step execution loop - abstracted reflection pattern
        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages, stop_sequences=self._stop_sequences
            )
            
            clean_message, thinking_ref = self._process_client_response(response, notes)
            
            if step_idx > 0:
                self._add_internal_message(
                    f"Step {step_idx + 1}/{self._max_steps}: {clean_message[:100]}...",
                    notes,
                    f"{self.get_name()} Progress"
                )
            
            if self.is_complete(clean_message):
                return self._format_completion_response(clean_message, thinking_ref)
            
            instruction = self._executor.extract_instruction(clean_message)
            if not instruction:
                feedback = "No valid instruction found. Please provide a valid instruction."
                messages = messages.add_assistant_utterance(clean_message)
                messages = messages.add_user_utterance(feedback)
                continue
            
            result, error = await self._executor.execute_operation(instruction, context)
            
            if error:
                feedback = self._executor.get_feedback_message(error)
                messages = messages.add_assistant_utterance(clean_message)
                messages = messages.add_user_utterance(feedback)
            elif self._executor.validate_result(result):
                artifact_id = create_hash(str(result))
                artifact = self._executor.transform_to_artifact(result, instruction, artifact_id)
                self._storage.store_artefact(artifact_id, artifact)
                
                self._add_internal_message(
                    f"Created {artifact.type} artifact: {artifact_id}",
                    notes,
                    "Artifact"
                )
                
                return f"Operation completed. Result: <artefact type='{artifact.type}'>{artifact_id}</artefact> <taskcompleted/>"
            else:
                feedback = "Invalid result. Please try again."
                messages = messages.add_assistant_utterance(clean_message)
                messages = messages.add_user_utterance(feedback)
        
        # For single-step agents, return whatever was produced (no reflection expected)
        if self._max_steps == 1:
            return f"{clean_message} {task_completed_tag}"

        self._add_internal_message(
            f"Max steps ({self._max_steps}) reached",
            notes,
            "Warning"
        )
        return f"Could not complete task within allowed steps. Please try rephrasing. {task_completed_tag}"
    
    @abstractmethod
    async def _query_custom(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        """Custom query implementation for complex agents."""
        pass
    
    def _format_completion_response(self, message: str, thinking_ref: Optional[str]) -> str:
        """Format final response when task is complete."""
        if self._output_tag:
            tag_name = self._output_tag.replace('```', '').replace('`', '')
            output = get_first_text_between_tags(message, tag_name, tag_name)
            if output:
                return output
        return message
    
    # === Standard Methods ===
    
    def get_name(self) -> str:
        return get_agent_name_from_class(self.__class__)
    
    @staticmethod
    @abstractmethod
    def get_info() -> str:
        """Brief description of what this agent does."""
        pass
    
    def get_description(self) -> str:
        return f"{self.get_info()}. Budget: {self._budget} calls."
    
    def get_budget(self) -> int:
        return self._budget
    
    def consume_budget(self) -> bool:
        if self._budget > 0:
            self._budget -= 1
            return True
        return False
    
    def reset_budget(self) -> None:
        self._budget = self._original_budget
    
    def get_taxonomy(self) -> AgentTaxonomy:
        """Get the taxonomy classification for this agent.
        
        Returns:
            AgentTaxonomy object describing the agent's classification
        """
        from yaaaf.components.agents.agent_taxonomies import get_agent_taxonomy
        return get_agent_taxonomy(self.__class__.__name__)
    
    def get_artifact_spec(self) -> AgentArtifactSpec:
        """Get the artifact specification for this agent.
        
        Returns:
            AgentArtifactSpec object describing what artifacts this agent accepts/produces
        """
        from yaaaf.components.data_types import get_agent_artifact_spec
        return get_agent_artifact_spec(self.__class__.__name__)
    
    def set_budget(self, budget: int) -> None:
        self._budget = budget
        self._original_budget = budget
    
    def get_opening_tag(self) -> str:
        return f"<{self.get_name()}>"
    
    def get_closing_tag(self) -> str:
        return f"</{self.get_name()}>"
    
    def is_complete(self, answer: str) -> bool:
        return any(tag in answer for tag in self._completing_tags)
    
    def _try_complete_prompt_with_artifacts(self, context: dict) -> str:
        """Try to complete prompt template with artifacts if available."""
        artifacts = context.get("artifacts", [])
        
        # Always try to complete with artifacts - if no variables exist, nothing happens
        if isinstance(self._system_prompt, PromptTemplate):
            return create_prompt_from_artefacts(
                artifacts,
                filename=getattr(self, '_artifact_filename', 'output.png'),
                prompt_with_model=getattr(self, '_system_prompt_with_model', None),
                prompt_without_model=self._system_prompt
            )
        
        return self._system_prompt
    
    # === Utility Methods ===
    
    def _add_internal_message(
        self, message: str, notes: Optional[List[Note]], prefix: str = "Message"
    ):
        """Add internal messages to notes."""
        if notes is not None:
            internal_note = Note(
                message=f"[{prefix}] {message}",
                artefact_id=None,
                agent_name=self.get_name(),
                model_name=getattr(self._client, "model", None),
                internal=True,
            )
            notes.append(internal_note)
    
    def _create_thinking_artifact(
        self, response: "ClientResponse", notes: Optional[List[Note]]
    ) -> Optional[str]:
        """Create thinking artifact if present."""
        if not response.thinking_content:
            return None
        
        thinking_id = create_hash(
            f"thinking_{self.get_name()}_{response.thinking_content}"
        )
        
        self._storage.store_artefact(
            thinking_id,
            Artefact(
                type=Artefact.Types.THINKING,
                description=f"Thinking process from {self.get_name()}",
                code=response.thinking_content,
                id=thinking_id,
            ),
        )
        
        if notes is not None:
            note = Note(
                message=f"[Thinking] Created thinking artifact: {thinking_id}",
                artefact_id=thinking_id,
                agent_name=self.get_name(),
                model_name=getattr(self._client, "model", None),
                internal=True,
            )
            notes.append(note)
        
        return f"<artefact type='thinking'>{thinking_id}</artefact>"
    
    def _process_client_response(
        self, response: "ClientResponse", notes: Optional[List[Note]] = None
    ) -> tuple[str, Optional[str]]:
        """Process client response and extract thinking artifacts."""
        thinking_artifact_ref = self._create_thinking_artifact(response, notes)
        return response.message, thinking_artifact_ref


# === Specialized Base Classes ===

class ToolBasedAgent(BaseAgent):
    """Base class for agents using ToolExecutors."""
    
    def __init__(self, client: "BaseClient", executor: "ToolExecutor"):
        super().__init__()
        self._client = client
        self._executor = executor
    
    async def _query_custom(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
        """ToolBasedAgent uses executor pattern."""
        raise NotImplementedError("ToolBasedAgent should use executor pattern")


class CustomAgent(BaseAgent):
    """Base class for agents with custom logic."""
    
    def __init__(self, client: "BaseClient"):
        super().__init__()
        self._client = client