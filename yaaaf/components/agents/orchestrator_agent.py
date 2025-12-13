import logging
import re
from typing import Dict, Any, Optional, TYPE_CHECKING
from yaaaf.components.agents.base_agent import CustomAgent

if TYPE_CHECKING:
    from yaaaf.components.agents.validation_agent import ValidationAgent
from yaaaf.components.agents.planner_agent import PlannerAgent
from yaaaf.components.agents.plan_artifact import PlanArtifact
from yaaaf.components.agents.artefacts import ArtefactStorage
from yaaaf.components.extractors.enhanced_goal_extractor import EnhancedGoalExtractor
from yaaaf.components.executors.workflow_executor import (
    WorkflowExecutor,
    ValidationError,
    ConditionError,
    ReplanRequiredException,
    UserDecisionRequiredException,
)
from yaaaf.components.executors.paused_execution import PausedExecutionException
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.client import BaseClient

_logger = logging.getLogger(__name__)


class OrchestratorAgent(CustomAgent):
    """Orchestrator that uses plan-driven execution with automatic replanning."""

    def __init__(
        self,
        client: BaseClient,
        agents: Dict[str, Any],
        validation_agent: Optional["ValidationAgent"] = None,
    ):
        """Initialize plan-driven orchestrator.

        Args:
            client: LLM client
            agents: Dictionary of available agents
            validation_agent: Optional validation agent for artifact validation
        """
        super().__init__(client)
        self.agents = agents
        self.goal_extractor = EnhancedGoalExtractor(client)
        self.planner = None  # Will be set from agents dict
        self.current_plan = None
        self.plan_executor = None
        self.artefact_storage = ArtefactStorage()
        self._max_replan_attempts = 3
        self._validation_agent = validation_agent
        self._original_goal = None  # Store for validation context

        # Extract planner from agents
        for agent_name, agent in agents.items():
            if isinstance(agent, PlannerAgent):
                self.planner = agent
                break

        if not self.planner:
            raise ValueError("PlannerAgent not found in available agents")

    async def query(self, messages: Messages, notes=None, stream_id=None) -> str:
        """Override query to accept stream_id parameter.
        
        Args:
            messages: User messages
            notes: Optional notes (not used)
            stream_id: Stream ID for tracking and real-time updates
            
        Returns:
            String representation of final result
        """
        return await self._query_custom(messages, notes, stream_id)

    async def _query_custom(self, messages: Messages, notes=None, stream_id=None) -> str:
        """Process messages using plan-driven approach.

        Args:
            messages: User messages
            notes: Optional notes (not used)
            stream_id: Stream ID for tracking and real-time updates

        Returns:
            String representation of final result
        """
        # Step 1: Extract goal and target artifact type
        goal_info = await self._extract_goal_and_type(messages)
        _logger.info(
            f"Extracted goal: {goal_info['goal']}, target type: {goal_info['artifact_type']}"
        )

        # Store original goal for validation context
        self._original_goal = goal_info['goal']
        
        # Update stream status
        if stream_id:
            from yaaaf.server.accessories import _stream_id_to_status
            if stream_id in _stream_id_to_status:
                _stream_id_to_status[stream_id].current_agent = "Planning execution workflow"
                _stream_id_to_status[stream_id].goal = goal_info['goal']

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
                    
                    # Add note showing the plan to the user
                    if notes is not None:
                        from yaaaf.components.data_types import Note
                        plan_note = Note(
                            message=f"📋 **Execution Plan Generated**\n\nI'll execute the following steps to {goal_info['goal']}:\n\n```yaml\n{self.current_plan}\n```\n",
                            artefact_id=plan_artifact.id,
                            agent_name="planner",
                        )
                        notes.append(plan_note)

                    # Create new executor with notes for streaming and status updates
                    self.plan_executor = WorkflowExecutor(
                        yaml_plan=self.current_plan,
                        agents=self.agents,
                        notes=notes,
                        stream_id=stream_id,
                        original_messages=messages,
                        validation_agent=self._validation_agent,
                        original_goal=self._original_goal,
                    )

                # Execute plan
                result = await self.plan_executor.execute(messages)

                # Verify result matches expected type
                if not self._verify_artifact_type(result, goal_info["artifact_type"]):
                    result_type = getattr(result, 'type', 'UNKNOWN')
                    raise ValidationError(
                        f"Expected {goal_info['artifact_type']} but got {result_type}"
                    )

                _logger.info("Plan executed successfully")
                # Return string representation of result
                if hasattr(result, "content"):
                    return result.content
                elif hasattr(result, "code"):
                    return result.code or str(result)
                else:
                    return str(result)

            except PausedExecutionException as e:
                # Execution paused for user input - save state and re-raise
                _logger.info(f"Execution paused for user input: {e.state.question_asked}")

                # Store paused state for later resumption
                from yaaaf.server.accessories import save_paused_state
                save_paused_state(stream_id, e.state)

                # Add a note to inform user that input is needed
                if notes is not None:
                    from yaaaf.components.data_types import Note
                    waiting_note = Note(
                        message=f"⏸️ **Waiting for your input:**\n\n{e.state.question_asked}\n\n<taskpaused/>",
                        artefact_id=None,
                        agent_name="userinputagent",  # Match frontend renderer tag name
                    )
                    notes.append(waiting_note)
                    _logger.info(f"Added waiting note for stream {stream_id}")

                # Re-raise to signal to server that execution is paused
                raise

            except ReplanRequiredException as e:
                # Validation-triggered replanning
                _logger.warning(
                    f"Validation triggered replan (attempt {attempt + 1}): "
                    f"asset={e.validation_result.asset_name}, "
                    f"reason={e.validation_result.reason}"
                )

                # Include suggested fix in error context for better replanning
                if e.validation_result.suggested_fix:
                    last_error = (
                        f"Validation failed for {e.validation_result.asset_name}: "
                        f"{e.validation_result.reason}. "
                        f"Suggested fix: {e.validation_result.suggested_fix}"
                    )
                else:
                    last_error = (
                        f"Validation failed for {e.validation_result.asset_name}: "
                        f"{e.validation_result.reason}"
                    )

                partial_results = e.completed_assets
                self.current_plan = None  # Force replanning

                # Add note about validation-triggered replan
                if notes is not None:
                    from yaaaf.components.data_types import Note
                    replan_note = Note(
                        message=f"🔄 **Replanning required**\n\nValidation issue with '{e.validation_result.asset_name}': {e.validation_result.reason}",
                        artefact_id=None,
                        agent_name="validation",
                    )
                    notes.append(replan_note)

            except UserDecisionRequiredException as e:
                # Need user input to proceed
                _logger.warning(
                    f"User decision required for {e.validation_result.asset_name}: "
                    f"{e.validation_result.reason}"
                )

                # Add note requesting user decision
                if notes is not None:
                    from yaaaf.components.data_types import Note
                    decision_note = Note(
                        message=(
                            f"❓ **Decision needed**\n\n"
                            f"Issue with '{e.validation_result.asset_name}': {e.validation_result.reason}\n\n"
                            f"Please provide guidance on how to proceed."
                        ),
                        artefact_id=None,
                        agent_name="validation",
                    )
                    notes.append(decision_note)

                # For now, treat as error and trigger replan with user's implicit guidance
                # In future, this could pause and wait for explicit user input
                last_error = (
                    f"User decision needed for {e.validation_result.asset_name}: "
                    f"{e.validation_result.reason}"
                )
                partial_results = e.completed_assets
                self.current_plan = None

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

        response = await self.planner.query(planner_messages)
        
        # Debug: Log the raw planner response
        _logger.info(f"Planner raw response: {response}")

        # Extract YAML plan from artifact
        yaml_plan = self._extract_yaml_from_artifact(response)

        if not yaml_plan:
            raise ValueError("Failed to extract valid YAML plan from planner artifact")

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

    def _extract_yaml_from_artifact(self, response: str) -> Optional[str]:
        """Extract YAML plan from artifact response."""
        import re
        
        # Parse artifact ID from response like: <artefact type='text'>1120040561809014270</artefact>
        artifact_match = re.search(r"<artefact type='[^']*'>([^<]+)</artefact>", response)
        if not artifact_match:
            _logger.warning("No artifact ID found in planner response")
            return None
            
        artifact_id = artifact_match.group(1).strip()
        _logger.info(f"Extracting plan from artifact: {artifact_id}")
        
        try:
            # Retrieve artifact from storage
            artifact = self.artefact_storage.retrieve_from_id(artifact_id)
            if not artifact:
                _logger.warning(f"Artifact {artifact_id} not found in storage")
                return None
                
            # Get content from artifact
            if hasattr(artifact, 'code') and artifact.code:
                content = artifact.code
            elif hasattr(artifact, 'data') and artifact.data:
                content = str(artifact.data)
            elif hasattr(artifact, 'content') and artifact.content:
                content = artifact.content
            else:
                content = str(artifact)
                
            _logger.info(f"Artifact content: {content}")
            
            # Extract YAML from content
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
            
        except Exception as e:
            _logger.error(f"Failed to retrieve artifact {artifact_id}: {e}")
            return None

    def _format_partial_results(self, partial_results: Dict[str, Any]) -> str:
        """Format partial results for replanning context."""
        if not partial_results:
            return "None"

        parts = []
        for asset_name, artifact in partial_results.items():
            artifact_type = getattr(artifact, 'type', 'UNKNOWN')
            artifact_summary = getattr(artifact, 'summary', None) or getattr(artifact, 'description', None) or 'completed'
            parts.append(
                f"- {asset_name}: {artifact_type} ({artifact_summary})"
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
                "TEXT": ["text", "TEXT", "string", "table", "TABLE"],  # Allow TABLE as valid for TEXT
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
