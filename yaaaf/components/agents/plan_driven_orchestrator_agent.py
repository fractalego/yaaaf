import logging
import re
from typing import Dict, Any, Optional, List
from yaaaf.components.agents.base_agent import CustomAgent
from yaaaf.components.agents.planner_agent import PlannerAgent
from yaaaf.components.agents.plan_artifact import PlanArtifact
from yaaaf.components.agents.artefacts import ArtefactStorage
from yaaaf.components.extractors.enhanced_goal_extractor import EnhancedGoalExtractor
from yaaaf.components.executors.workflow_executor import (
    WorkflowExecutor,
    ValidationError,
    ConditionError,
)
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class OrchestratorAgent(CustomAgent):
    """Orchestrator that uses plan-driven execution with automatic replanning."""

    def __init__(self, client: BaseClient, agents: Dict[str, Any]):
        """Initialize plan-driven orchestrator.

        Args:
            client: LLM client
            agents: Dictionary of available agents
        """
        super().__init__(client)
        self.agents = agents
        self.goal_extractor = EnhancedGoalExtractor(client)
        self.planner = None  # Will be set from agents dict
        self.current_plan = None
        self.plan_executor = None
        self.artefact_storage = ArtefactStorage()
        self._max_replan_attempts = 3

        # Extract planner from agents
        for agent_name, agent in agents.items():
            if isinstance(agent, PlannerAgent):
                self.planner = agent
                break

        if not self.planner:
            raise ValueError("PlannerAgent not found in available agents")

    async def _query_custom(self, messages: Messages, notes=None) -> str:
        """Process messages using plan-driven approach.

        Args:
            messages: User messages
            notes: Optional notes (not used)

        Returns:
            String representation of final result
        """
        # Step 1: Extract goal and target artifact type
        goal_info = await self._extract_goal_and_type(messages)
        _logger.info(
            f"Extracted goal: {goal_info['goal']}, target type: {goal_info['artifact_type']}"
        )

        # Step 2: Execute with replanning on failure
        last_error = None
        partial_results = {}

        for attempt in range(self._max_replan_attempts):
            try:
                # Generate or regenerate plan
                if not self.current_plan or last_error:
                    self.current_plan = await self._generate_plan(
                        goal=goal_info["goal"],
                        target_type=goal_info["artifact_type"],
                        messages=messages,
                        error_context=last_error,
                        partial_results=partial_results,
                    )

                    # Store plan as artifact
                    plan_artifact = PlanArtifact(
                        plan_yaml=self.current_plan,
                        goal=goal_info["goal"],
                        target_artifact_type=goal_info["artifact_type"],
                    )
                    self.artefact_storage.store_artefact(
                        plan_artifact.id, plan_artifact
                    )
                    _logger.info(f"Generated plan artifact: {plan_artifact.id}")

                    # Create new executor
                    self.plan_executor = WorkflowExecutor(
                        self.current_plan, self.agents
                    )

                # Execute plan
                result = await self.plan_executor.execute(messages)

                # Verify result matches expected type
                if not self._verify_artifact_type(result, goal_info["artifact_type"]):
                    raise ValidationError(
                        f"Expected {goal_info['artifact_type']} but got {result.type}"
                    )

                _logger.info("Plan executed successfully")
                # Return string representation of result
                if hasattr(result, "content"):
                    return result.content
                elif hasattr(result, "code"):
                    return result.code or str(result)
                else:
                    return str(result)

            except (ValidationError, ConditionError) as e:
                _logger.warning(f"Plan execution failed (attempt {attempt + 1}): {e}")
                last_error = str(e)
                partial_results = (
                    self.plan_executor.get_completed_assets()
                    if self.plan_executor
                    else {}
                )
                self.current_plan = None  # Force replanning

            except Exception as e:
                _logger.error(f"Unexpected error in plan execution: {e}")
                last_error = f"Unexpected error: {str(e)}"
                partial_results = (
                    self.plan_executor.get_completed_assets()
                    if self.plan_executor
                    else {}
                )
                self.current_plan = None

        # All attempts failed
        raise RuntimeError(
            f"Failed to execute plan after {self._max_replan_attempts} attempts. Last error: {last_error}"
        )

    async def _extract_goal_and_type(self, messages: Messages) -> Dict[str, str]:
        """Extract goal and target artifact type from messages."""
        return await self.goal_extractor.extract(messages)

    async def _generate_plan(
        self,
        goal: str,
        target_type: str,
        messages: Messages,
        error_context: Optional[str] = None,
        partial_results: Optional[Dict] = None,
    ) -> str:
        """Generate execution plan using planner agent."""

        # Build planning request
        if error_context and partial_results:
            # Replanning with context
            planning_request = f"""
The following plan failed during execution:

```yaml
{self.current_plan if self.current_plan else "No previous plan"}
```

Error: {error_context}

Completed assets so far:
{self._format_partial_results(partial_results)}

Please create a revised plan that:
1. Uses the already completed assets where possible
2. Works around the error condition
3. Still achieves the goal: {goal}
4. Produces a final artifact of type: {target_type}

Original user request: {messages.utterances[-1].content}
"""
        else:
            # Initial planning
            planning_request = f"""
Create an execution plan for this goal:

Goal: {goal}
Target Artifact Type: {target_type}

The plan MUST:
1. End with an agent that produces {target_type} artifacts
2. Include all necessary data transformations
3. Handle the specific requirements of: {goal}

User Context: {messages.utterances[-1].content}
"""

        # Call planner agent
        planner_messages = Messages(
            utterances=[Utterance(role="user", content=planning_request)]
        )

        response = await self.planner.aprocess(planner_messages)

        # Extract YAML plan from response
        yaml_plan = self._extract_yaml_from_response(response)

        if not yaml_plan:
            raise ValueError("Failed to extract valid YAML plan from planner response")

        return yaml_plan

    def _extract_yaml_from_response(self, response: Any) -> Optional[str]:
        """Extract YAML content from planner response."""
        if hasattr(response, "content"):
            content = response.content
        elif hasattr(response, "artefacts") and response.artefacts:
            # Get from artifacts
            artifact = response.artefacts[-1]
            content = artifact.code if artifact.code else ""
        else:
            content = str(response)

        # Find YAML block
        yaml_match = re.search(r"```yaml\s*(.*?)```", content, re.DOTALL)
        if yaml_match:
            return yaml_match.group(1).strip()

        # Try to find assets: block directly
        if "assets:" in content:
            # Extract from assets: to end or next ```
            assets_start = content.find("assets:")
            assets_end = content.find("```", assets_start)
            if assets_end == -1:
                assets_end = len(content)
            return content[assets_start:assets_end].strip()

        return None

    def _format_partial_results(self, partial_results: Dict[str, Any]) -> str:
        """Format partial results for replanning context."""
        if not partial_results:
            return "None"

        parts = []
        for asset_name, artifact in partial_results.items():
            parts.append(
                f"- {asset_name}: {artifact.type} ({artifact.summary or artifact.description or 'completed'})"
            )

        return "\n".join(parts)

    def _verify_artifact_type(self, artifact: Any, expected_type: str) -> bool:
        """Verify artifact matches expected type."""
        if hasattr(artifact, "type"):
            artifact_type = (
                artifact.type.upper()
                if isinstance(artifact.type, str)
                else str(artifact.type)
            )

            # Handle type mappings
            type_mappings = {
                "TABLE": ["table", "TABLE", "dataframe"],
                "IMAGE": ["image", "IMAGE", "chart", "plot"],
                "TEXT": ["text", "TEXT", "string"],
                "MODEL": ["model", "MODEL", "sklearn"],
                "TODO_LIST": ["todo-list", "TODO_LIST", "todo_list"],
                "PLAN": ["plan", "PLAN"],
            }

            expected_upper = expected_type.upper()
            if expected_upper in type_mappings:
                return any(
                    artifact_type.lower() == t.lower()
                    for t in type_mappings[expected_upper]
                )

        return True  # Default to accepting if we can't determine type

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Orchestrates agents using AI-generated execution plans"

    def get_description(self) -> str:
        """Get detailed description."""
        return f"""
Plan-Driven Orchestrator: {self.get_info()}.

This orchestrator:
1. Extracts user goals and required output types
2. Generates execution plans using the PlannerAgent
3. Executes plans deterministically 
4. Automatically replans on failures
5. Stores plans and results as artifacts

The orchestrator ensures robust execution through automatic error recovery and replanning.
"""
