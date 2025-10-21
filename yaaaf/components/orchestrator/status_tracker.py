"""
Status tracking utilities for the orchestrator.
Handles todo artifacts, progress tracking, and status updates.
"""
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from yaaaf.components.extractors.status_extractor import StatusExtractor

_logger = logging.getLogger(__name__)


class StatusTracker:
    """Manages task progress, todo artifacts, and status updates."""
    
    def __init__(self, status_extractor: "StatusExtractor"):
        self._status_extractor = status_extractor
        self._current_todo_artifact_id: Optional[str] = None
        self._needs_replanning: bool = False
        self._current_stream_id: Optional[str] = None
    
    def reset_for_new_query(self, stream_id: Optional[str] = None) -> None:
        """Reset state for a new query."""
        self._current_todo_artifact_id = None
        self._needs_replanning = False
        self._current_stream_id = stream_id
    
    def set_todo_artifact(self, artifact_id: str) -> None:
        """Set the current todo artifact ID."""
        self._current_todo_artifact_id = artifact_id
        self._needs_replanning = False
        _logger.info(f"[STATUS_TRACKER] Stored todo artifact ID: {artifact_id}, has_todo_artifact: {self.has_todo_artifact}")
    
    def trigger_replanning(self) -> None:
        """Trigger replanning by marking that replanning is needed."""
        self._needs_replanning = True
        # Don't clear the todo artifact ID - we'll update the same artifact
        _logger.info(f"[STATUS_TRACKER] Plan change detected - triggering replanning. Keeping todo artifact: {self._current_todo_artifact_id}")
    
    async def update_task_status(self, response: str, agent_name: str) -> Optional[str]:
        """Update task status based on agent response."""
        if not self._current_todo_artifact_id:
            _logger.warning(f"[STATUS_TRACKER] No todo artifact ID set, cannot update status for agent: {agent_name}")
            return None
        
        _logger.info(
            f"[STATUS_TRACKER] Calling status extractor for agent {agent_name} with artifact ID: {self._current_todo_artifact_id}"
        )
        
        updated_artifact_id, needs_replanning = await self._status_extractor.extract_and_update_status(
            response, agent_name, self._current_todo_artifact_id
        )
        
        _logger.info(
            f"Status extractor returned: updated_id={updated_artifact_id}, needs_replanning={needs_replanning}"
        )
        
        if needs_replanning:
            self.trigger_replanning()
            return None
        elif updated_artifact_id != self._current_todo_artifact_id:
            self._current_todo_artifact_id = updated_artifact_id
            _logger.info(f"Updated todo artifact ID: {updated_artifact_id}")
        
        return updated_artifact_id
    
    async def mark_tasks_completed(self, response: str, orchestrator_name: str) -> None:
        """Mark tasks as completed when orchestrator finishes."""
        if not self._current_todo_artifact_id:
            return
        
        _logger.info(
            f"Task completed - calling status extractor with response: {response[:200]}..."
        )
        
        updated_artifact_id, needs_replanning = await self._status_extractor.extract_and_update_status(
            response, orchestrator_name, self._current_todo_artifact_id
        )
        
        _logger.info(
            f"Status extractor returned: updated_id={updated_artifact_id}, needs_replanning={needs_replanning}"
        )
        
        if updated_artifact_id != self._current_todo_artifact_id:
            self._current_todo_artifact_id = updated_artifact_id
            _logger.info(f"Updated todo artifact ID: {updated_artifact_id}")
    
    def get_task_progress_section(self) -> str:
        """Generate task progress section for system prompt."""
        if self._needs_replanning:
            return '''
== CURRENT TASK PROGRESS ==
**REPLANNING REQUIRED**: New information detected that requires updating the plan

### Current Status
- [🔄] **Creating new todo list** ←─ CURRENT STEP

### Step Context
Currently investigating: Plan revision based on new discoveries
Previous plan needs updating due to new information from sub-agent response.
'''
        
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
        
        return f'''
== CURRENT TASK PROGRESS ==
**Step {current_step} of {total_steps}**: {current_desc}

### Todo List
{markdown_todo}

### Step Context
Currently investigating: {current_desc}
'''
    
    def update_stream_status(self, goal: Optional[str] = None, current_agent: Optional[str] = None) -> None:
        """Update stream status if stream ID is available."""
        if not self._current_stream_id:
            return
        
        try:
            from yaaaf.server.accessories import update_stream_status
            update_stream_status(
                self._current_stream_id,
                goal=goal,
                current_agent=current_agent
            )
        except Exception as e:
            _logger.warning(f"Failed to update stream status: {e}")
    
    @property
    def needs_replanning(self) -> bool:
        """Check if replanning is needed."""
        return self._needs_replanning
    
    @property
    def has_todo_artifact(self) -> bool:
        """Check if there's a current todo artifact."""
        return self._current_todo_artifact_id is not None