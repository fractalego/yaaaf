"""
Agent management utilities for the orchestrator.
Handles agent registration, budget management, and routing.
"""
import logging
import re
from typing import Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from yaaaf.components.agents.base_agent import BaseAgent

_logger = logging.getLogger(__name__)


class AgentManager:
    """Manages agent registration, budgets, and routing."""
    
    def __init__(self):
        self._agents: Dict[str, "BaseAgent"] = {}
        self._stop_sequences: list[str] = []
    
    def register_agent(self, agent: "BaseAgent") -> None:
        """Register an agent with the manager."""
        opening_tag = agent.get_opening_tag()
        if opening_tag in self._agents:
            raise ValueError(f"Agent with tag {opening_tag} already exists.")
        
        self._agents[opening_tag] = agent
        self._stop_sequences.append(agent.get_closing_tag())
        
        _logger.info(
            f"Registered agent: {agent.get_name()} (tag: {opening_tag})"
        )
    
    def reset_all_budgets(self) -> None:
        """Reset budgets for all agents."""
        for agent in self._agents.values():
            agent.reset_budget()
        _logger.info("Reset budgets for all agents")
    
    def get_available_agents(self) -> Dict[str, "BaseAgent"]:
        """Get agents that still have budget remaining."""
        return {
            tag: agent
            for tag, agent in self._agents.items()
            if agent.get_budget() > 0
        }
    
    def route_to_agent(self, response: str) -> Tuple[Optional["BaseAgent"], Optional[str]]:
        """Route response to appropriate agent based on tags."""
        available_agents = self.get_available_agents()
        
        for _, agent in available_agents.items():
            opening_tag = agent.get_opening_tag().replace(">", ".*?>")
            matches = re.findall(
                rf"{opening_tag}(.+)", response, re.DOTALL | re.MULTILINE
            )
            if matches:
                return agent, matches[0]
        
        return None, None
    
    def simplify_agent_tags(self, text: str) -> str:
        """Simplify agent tags in text for frontend display."""
        available_agents = self.get_available_agents()
        for _, agent in available_agents.items():
            opening_tag = agent.get_opening_tag().replace(">", ".*?>")
            # This is to avoid confusing the frontend
            text = re.sub(
                rf"{opening_tag}", agent.get_opening_tag(), text, flags=re.DOTALL
            )
        return text
    
    def get_stop_sequences(self) -> list[str]:
        """Get all agent stop sequences."""
        return self._stop_sequences.copy()
    
    def get_agent_descriptions(self) -> str:
        """Get formatted descriptions of available agents."""
        available_agents = self.get_available_agents()
        descriptions = []
        
        for agent in available_agents.values():
            descriptions.append(
                f"* {agent.get_description().strip()}"
                f" (Budget: {agent.get_budget()} calls)\n"
            )
        
        return "\n".join(descriptions)
    
    def get_agent_tags_list(self) -> str:
        """Get formatted list of agent tags."""
        available_agents = self.get_available_agents()
        tags = []
        
        for agent in available_agents.values():
            tags.append(
                agent.get_opening_tag().strip() + agent.get_closing_tag().strip()
            )
        
        return "\n".join(tags)
    
    def get_budget_info(self) -> str:
        """Get current budget information for all agents."""
        available_agents = self.get_available_agents()
        budget_lines = ["Current agent budgets (remaining calls):"]
        
        for agent in available_agents.values():
            budget_lines.append(
                f"• {agent.get_name()}: {agent.get_budget()} calls remaining"
            )
        
        return "\n".join(budget_lines)