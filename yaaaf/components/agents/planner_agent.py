import logging
from typing import List, Dict, Any, Optional

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors.planner_executor import PlannerExecutor
from yaaaf.components.agents.prompts import planner_agent_prompt_template
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import AGENT_ARTIFACT_SPECS
from yaaaf.components.retrievers.planner_example_retriever import PlannerExampleRetriever

_logger = logging.getLogger(__name__)


class PlannerAgent(ToolBasedAgent):
    """Agent that creates execution DAGs showing data flow from sources to sinks."""

    def __init__(self, client: BaseClient, available_agents: List[Dict[str, Any]]):
        """Initialize planner agent.

        Args:
            client: LLM client for generating plans
            available_agents: List of available agents with their taxonomies
        """
        super().__init__(client, PlannerExecutor(available_agents))

        # Create agent descriptions with taxonomy info
        agent_descriptions = self._create_agent_descriptions(available_agents)

        # Partially complete the prompt template with agent_descriptions
        # Use replace() instead of complete() to keep {examples} as a placeholder
        self._system_prompt_template = planner_agent_prompt_template.prompt.replace(
            "{agent_descriptions}", agent_descriptions
        )
        self._system_prompt = self._system_prompt_template  # Will be completed at query time

        # Initialize the example retriever (singleton, loads dataset once)
        self._example_retriever = PlannerExampleRetriever()

        self._output_tag = "```yaml"
        self.set_budget(1)

        # Store the current query for use in prompt completion
        self._current_query: Optional[str] = None

    def _create_agent_descriptions(self, available_agents: List[Dict[str, Any]]) -> str:
        """Create formatted descriptions of available agents with their taxonomies and artifact handling."""
        descriptions = []
        
        for agent_info in available_agents:
            name = agent_info.get("name", "Unknown")
            description = agent_info.get("description", "No description")
            taxonomy = agent_info.get("taxonomy")
            
            desc_parts = [f"{name}:"]
            desc_parts.append(f"  {description}")
            
            # Get artifact specification from the centralized definitions
            try:
                artifact_spec = AGENT_ARTIFACT_SPECS.get(name)
                if artifact_spec:
                    # Format accepts
                    if not artifact_spec.accepts:
                        accepts_str = "None (source)"
                    else:
                        accepts_str = "/".join(t.value for t in artifact_spec.accepts)
                    
                    # Format produces
                    produces_str = "/".join(t.value for t in artifact_spec.produces)
                    
                    desc_parts.append(f"  - Accepts: {accepts_str}")
                    desc_parts.append(f"  - Produces: {produces_str}")
                else:
                    desc_parts.append(f"  - Accepts: Unknown")
                    desc_parts.append(f"  - Produces: Unknown")
            except Exception as e:
                _logger.warning(f"Could not get artifact spec for {name}: {e}")
                desc_parts.append(f"  - Accepts: Unknown")
                desc_parts.append(f"  - Produces: Unknown")
            
            if taxonomy:
                desc_parts.append(f"  - Data Flow: {taxonomy.data_flow.value}")
                desc_parts.append(f"  - Interaction: {taxonomy.interaction_mode.value}")
                desc_parts.append(f"  - Output: {taxonomy.output_permanence.value}")
            
            descriptions.append("\n".join(desc_parts))
        
        return "\n\n".join(descriptions)

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Creates execution workflows showing optimal data flow paths"

    def get_description(self) -> str:
        return f"""
Planner agent: {self.get_info()}.
This agent can:
- Analyze query requirements
- Identify necessary source agents (extractors)
- Plan transformation steps (processors)
- Route data to appropriate sinks (outputs)
- Generate YAML workflow showing execution flow with conditions

To call this agent write {self.get_opening_tag()} PLANNING_REQUEST {self.get_closing_tag()}
Describe what goal needs to be achieved and any constraints.

The agent will output a workflow in YAML format with asset-based dependencies.
        """

    def _try_complete_prompt_with_artifacts(self, context: dict) -> str:
        """Complete prompt template with dynamic examples based on query.

        Overrides base class to inject relevant examples from the planner dataset
        using BM25 retrieval based on the user's query.
        """
        # Extract user query from context or messages
        query = ""
        if "messages" in context:
            messages = context["messages"]
            if hasattr(messages, "utterances") and messages.utterances:
                # Get the last user message
                for utterance in reversed(messages.utterances):
                    if utterance.role == "user":
                        query = utterance.content
                        break

        # Retrieve relevant examples
        if query:
            examples = self._example_retriever.format_examples_for_prompt(query, topn=3)
            _logger.debug(f"Retrieved examples for query: {query[:100]}...")
        else:
            examples = "No examples available for empty query."
            _logger.warning("No query found for example retrieval")

        # Complete the prompt with examples
        completed_prompt = self._system_prompt_template.replace("{examples}", examples)

        return completed_prompt