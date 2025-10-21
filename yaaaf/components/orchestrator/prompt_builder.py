"""
System prompt building utilities for the orchestrator.
Handles dynamic prompt generation with budget info, status, and progress.
"""
import logging
from typing import Optional, TYPE_CHECKING

from yaaaf.components.agents.prompts import orchestrator_prompt_template
from yaaaf.components.agents.settings import task_completed_tag

if TYPE_CHECKING:
    from yaaaf.components.orchestrator.agent_manager import AgentManager
    from yaaaf.components.orchestrator.status_tracker import StatusTracker
    from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds dynamic system prompts for the orchestrator."""
    
    def __init__(self, agent_manager: "AgentManager", status_tracker: "StatusTracker", client: "BaseClient"):
        self._agent_manager = agent_manager
        self._status_tracker = status_tracker
        self._client = client
    
    def build_system_prompt(self, goal: str) -> str:
        """Build complete system prompt with current context."""
        # Get training cutoff information
        training_cutoff_info = self._get_training_cutoff_info()
        
        # Get agent information
        agents_list = self._agent_manager.get_agent_descriptions()
        all_tags_list = self._agent_manager.get_agent_tags_list()
        budget_info = self._agent_manager.get_budget_info()
        
        # Get status and progress information
        status_info = self._get_system_status()
        task_progress_section = self._status_tracker.get_task_progress_section()
        
        return orchestrator_prompt_template.complete(
            training_cutoff_info=training_cutoff_info,
            agents_list=agents_list,
            all_tags_list=all_tags_list,
            budget_info=budget_info,
            status_info=status_info,
            task_progress_section=task_progress_section,
            goal=goal,
            task_completed_tag=task_completed_tag,
        )
    
    def _get_training_cutoff_info(self) -> str:
        """Get training cutoff information from client."""
        if hasattr(self._client, "get_training_cutoff_date"):
            cutoff_date = self._client.get_training_cutoff_date()
            if cutoff_date:
                return f"Your training date cutoff is {cutoff_date}. You have been trained to know only information before that date."
        return ""
    
    def _get_system_status(self) -> str:
        """Collect status information from all agents."""
        status_entries = []
        available_agents = self._agent_manager.get_available_agents()
        
        for agent in available_agents.values():
            if hasattr(agent, "get_status_info"):
                status = agent.get_status_info()
                if status.strip():
                    status_entries.append(f"• {agent.get_name()}: {status}")
        
        if not status_entries:
            return "No special conditions reported by agents."
        
        return "\n".join(status_entries)