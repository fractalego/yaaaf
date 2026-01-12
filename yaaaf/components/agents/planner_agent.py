import logging
from typing import List, Dict, Any, Optional

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors.planner_executor import PlannerExecutor
from yaaaf.components.agents.prompts import planner_agent_prompt_template
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import AGENT_ARTIFACT_SPECS, Messages, Utterance
from yaaaf.components.retrievers.planner_example_retriever import PlannerExampleRetriever
from yaaaf.components.validators.replan_context import ReplanContext

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

        # Extract class names for retriever filtering
        available_class_names = [
            agent.get("class_name", agent.get("name"))
            for agent in available_agents
        ]

        # Initialize the example retriever with agent filtering
        # Only examples using a subset of available agents will be indexed
        self._example_retriever = PlannerExampleRetriever(available_class_names)

        self._output_tag = "```yaml"
        self.set_budget(1)

        # Store the current query for use in prompt completion
        self._current_query: Optional[str] = None

    def _create_agent_descriptions(self, available_agents: List[Dict[str, Any]]) -> str:
        """Create formatted descriptions of available agents with their taxonomies and artifact handling."""
        descriptions = []
        
        for agent_info in available_agents:
            name = agent_info.get("name", "Unknown")
            class_name = agent_info.get("class_name", name)  # Use class name for spec lookup
            description = agent_info.get("description", "No description")
            taxonomy = agent_info.get("taxonomy")

            desc_parts = [f"{name}:"]
            desc_parts.append(f"  {description}")

            # Get artifact specification from the centralized definitions
            # Use class_name (e.g., "BraveSearchAgent") not name (e.g., "brave_search")
            try:
                artifact_spec = AGENT_ARTIFACT_SPECS.get(class_name)
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
                _logger.warning(f"Could not get artifact spec for {class_name}: {e}")
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

    async def plan_continuation(
        self, replan_context: ReplanContext, notes: Optional[List] = None
    ) -> str:
        """Generate a continuation plan that builds on a failed plan.

        Args:
            replan_context: Context about the failed plan and what to fix
            notes: Optional notes list

        Returns:
            YAML plan string that references prior artifacts
        """
        _logger.info(
            f"Generating continuation plan (iteration {replan_context.iteration}) "
            f"for goal: {replan_context.original_goal[:100]}"
        )

        # Build a detailed prompt for continuation planning
        continuation_prompt = self._build_continuation_prompt(replan_context)

        # Create messages
        messages = Messages()
        messages.utterances.append(
            Utterance(role="user", content=continuation_prompt)
        )

        # Query the planner
        result = await self.query(messages, notes=notes)

        return result

    def _build_continuation_prompt(self, replan_context: ReplanContext) -> str:
        """Build a prompt for continuation planning.

        Args:
            replan_context: Context about the failed execution

        Returns:
            Prompt string
        """
        # Format completed artifacts
        completed_artifacts_desc = []
        for artifact in replan_context.completed_artifacts:
            completed_artifacts_desc.append(
                f"  - {artifact.name}: {artifact.description} "
                f"(type={artifact.type}, id={artifact.id[:12]}..., agent={artifact.agent_name})"
            )
        completed_artifacts_str = "\n".join(completed_artifacts_desc) if completed_artifacts_desc else "  None"

        # Format failed artifact
        failed_artifact = replan_context.failed_artifact
        failed_desc = (
            f"{failed_artifact.name}: {failed_artifact.description} "
            f"(type={failed_artifact.type}, agent={failed_artifact.agent_name})"
        )

        # Build the prompt
        prompt = f"""CONTINUATION PLANNING REQUEST (Iteration {replan_context.iteration})

**Original Goal:** {replan_context.original_goal}

**What Happened:**
A previous plan was executed but failed at one step. You need to create a NEW plan that:
1. References artifacts from the prior plan (using external_artifact_id)
2. Adds new steps to fix the failure
3. Achieves the original goal

**Prior Plan Execution Summary:**

Successfully Completed Steps:
{completed_artifacts_str}

Failed Step:
  - {failed_desc}

**Failure Information:**
Type: {replan_context.failure_type.value}
Summary: {replan_context.failure_summary}
Details: {replan_context.failure_details.error_message}

**How to Reference Prior Artifacts:**
To reuse an artifact from the prior plan, create an asset node WITHOUT an agent field:

```yaml
assets:
  # Reference to prior artifact (no agent field!)
  previous_analysis:
    type: text  # REQUIRED: type field is always required
    external_artifact_id: "{replan_context.completed_artifacts[0].id if replan_context.completed_artifacts else 'artifact_id_here'}"
    description: "Analysis from first attempt"

  # New step that uses the prior artifact
  fix_the_issue:
    agent: answerer
    type: text  # REQUIRED: type field is always required
    description: "Correct the issue based on failure analysis"
    inputs: [previous_analysis]
```

**CRITICAL REQUIREMENTS:**
- ALL assets (both external references and new steps) MUST have a `type` field
- External artifact references: require `external_artifact_id` and `type` (NO `agent`)
- New execution steps: require `agent`, `type`, and `description`

**Your Task:**
Generate a continuation plan that:
1. References relevant completed artifacts using external_artifact_id (NO agent field for these!)
2. Analyzes why the failed step didn't work
3. Creates new steps to fix the issue and achieve the goal
4. Uses appropriate agents from the available set
5. ENSURES ALL assets have a `type` field (text, table, image, etc.)

Please provide the complete YAML workflow."""

        return prompt