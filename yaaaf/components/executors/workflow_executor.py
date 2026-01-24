import logging
import yaml
import re
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.paused_execution import (
    PausedExecutionException,
    PausedExecutionState,
)
from yaaaf.components.validators.validation_result import ValidationResult
from yaaaf.components.validators.replan_context import (
    ReplanContext,
    ArtifactMetadata,
    FailureType,
    FailureDetails,
)
from yaaaf.components.validators.failure_analyzer import create_failure_summary
from yaaaf.components.executors.loop_config import (
    LoopConfig,
    LoopIterationResult,
    LoopExitCondition,
    ExitConditionType,
)

if TYPE_CHECKING:
    from yaaaf.components.agents.validation_agent import ValidationAgent

_logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when asset validation fails."""

    pass


class ConditionError(Exception):
    """Raised when condition evaluation fails."""

    pass


class ReplanRequiredException(Exception):
    """Raised when validation fails and replanning is needed."""

    def __init__(self, validation_result: ValidationResult, completed_assets: Dict[str, str], failed_asset_result: str = ""):
        self.validation_result = validation_result
        self.completed_assets = completed_assets
        self.failed_asset_result = failed_asset_result
        super().__init__(f"Replan required for {validation_result.asset_name}: {validation_result.reason}")


class UserDecisionRequiredException(Exception):
    """Raised when validation fails and user input is needed."""

    def __init__(self, validation_result: ValidationResult, completed_assets: Dict[str, str]):
        self.validation_result = validation_result
        self.completed_assets = completed_assets
        super().__init__(f"User decision required for {validation_result.asset_name}: {validation_result.reason}")


class WorkflowExecutor:
    """Executes a YAML workflow plan by coordinating agents."""

    def __init__(
        self,
        yaml_plan: str,
        agents: Dict[str, Any],
        notes: List[Any] = None,
        stream_id: str = None,
        original_messages: Optional[Messages] = None,
        validation_agent: Optional["ValidationAgent"] = None,
        original_goal: Optional[str] = None,
        disable_user_prompts: bool = False,
        cached_results: Optional[Dict[str, str]] = None,
        env_path: Optional[str] = None,
        working_dir: Optional[str] = None,
        disable_validation_replan: bool = False,
    ):
        """Initialize workflow executor.

        Args:
            yaml_plan: YAML workflow definition
            agents: Dictionary mapping agent names to agent instances
            notes: Optional list to append execution progress notes
            stream_id: Optional stream ID for status updates
            original_messages: Optional original user messages (needed for pause/resume)
            validation_agent: Optional validation agent for artifact validation
            original_goal: Original user goal for validation context
            disable_user_prompts: If True, skip user prompts on validation failure and replan instead
            cached_results: Optional dict of asset_name -> result_string from previous execution
                           Assets with cached results will be skipped (reused)
            env_path: Optional path to Python virtual environment for bash commands
            working_dir: Optional working directory for file operations (code_edit)
            disable_validation_replan: If True, validation failures will not trigger replanning
                                      (used for loop bodies where validation is handled by the loop)
        """
        self.yaml_plan = yaml_plan  # Store raw YAML for state persistence
        self.plan = yaml.safe_load(yaml_plan)
        self.agents = agents
        # Pre-populate with cached results if provided
        self.asset_results = cached_results.copy() if cached_results else {}
        self.artefact_storage = ArtefactStorage()
        self._execution_order = []
        self._notes = notes if notes is not None else []
        self._stream_id = stream_id
        self._original_messages = original_messages
        self._validation_agent = validation_agent
        self._original_goal = original_goal
        self._disable_user_prompts = disable_user_prompts
        self._env_path = env_path
        self._working_dir = working_dir
        self._disable_validation_replan = disable_validation_replan
        self._build_execution_graph()

    def _build_execution_graph(self):
        """Build execution order from dependencies."""
        assets = self.plan.get("assets", {})

        # Build dependency graph
        dependencies = {}
        for asset_name, asset_config in assets.items():
            inputs = asset_config.get("inputs", [])

            # Filter out special loop inputs - they're not DAG dependencies
            # __previous__* references previous iteration (not a dependency in this iteration)
            # __loop_input__* references parent scope (injected externally)
            real_dependencies = [
                inp for inp in inputs
                if not inp.startswith("__previous__") and not inp.startswith("__loop_input__")
            ]

            dependencies[asset_name] = real_dependencies

        # Debug: Log the dependency graph
        _logger.info(f"Dependency graph: {dependencies}")

        # Topological sort
        self._execution_order = self._topological_sort(dependencies)
        
        # Debug: Log the execution order
        _logger.info(f"Execution order: {self._execution_order}")

        if not self._execution_order:
            raise ValueError("Invalid workflow: circular dependencies detected")
            
        # Validate type compatibility across the workflow
        self._validate_workflow_type_compatibility()
        
        # Validate plan uses correct agent output types
        self._validate_plan_agent_types()

    def _topological_sort(self, dependencies: Dict[str, List[str]]) -> List[str]:
        """Perform topological sort on dependencies."""
        # Calculate in-degrees (how many dependencies each node has)
        in_degree = {node: len(deps) for node, deps in dependencies.items()}

        # Find nodes with no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for nodes that depend on this one
            for other_node, deps in dependencies.items():
                if node in deps:
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)

        # Return result if all nodes were processed
        return result if len(result) == len(dependencies) else []

    async def execute(self, messages: Messages) -> Artefact:
        """Execute the workflow plan.

        Args:
            messages: User messages/context

        Returns:
            Final artifact produced by the workflow
        """
        # Execute each asset in order
        for asset_name in self._execution_order:
            asset_config = self.plan["assets"][asset_name]

            # Check if asset is already cached (from previous execution)
            if asset_name in self.asset_results:
                _logger.info(f"Reusing cached result for asset '{asset_name}'")
                # Add note about reusing cached asset
                if self._notes is not None:
                    from yaaaf.components.data_types import Note
                    reuse_note = Note(
                        message=f"♻️ Reusing cached result for '{asset_name}'",
                        artefact_id=None,
                        agent_name="workflow",
                    )
                    self._notes.append(reuse_note)
                continue

            # Check for external artifact reference (from prior plan)
            if "external_artifact_id" in asset_config and "agent" not in asset_config:
                self._load_external_artifact(asset_name, asset_config)
                continue

            # Check for loop node
            if asset_config.get("type") == "loop":
                await self._execute_loop(asset_name, asset_config, messages)
                continue

            # Check conditions
            if not self._evaluate_conditions(asset_name, asset_config):
                _logger.info(f"Skipping {asset_name} due to conditions")
                continue

            # Gather input artifacts
            inputs = self._gather_inputs(asset_config.get("inputs", []))

            # Execute agent
            try:
                agent_name = asset_config["agent"]
                if agent_name not in self.agents:
                    raise ValueError(f"Agent {agent_name} not found")

                agent = self.agents[agent_name]
                
                # Update stream status
                if self._stream_id:
                    from yaaaf.server.accessories import _stream_id_to_status
                    if self._stream_id in _stream_id_to_status:
                        _stream_id_to_status[self._stream_id].current_agent = asset_config.get("description", f"Executing {asset_name}")
                        _stream_id_to_status[self._stream_id].goal = f"Step: {asset_name}"
                        _logger.info(f"Updated stream status to: {asset_config.get('description')} - goal: {asset_name}")
                
                # Add progress note
                if self._notes is not None:
                    from yaaaf.components.data_types import Note
                    progress_note = Note(
                        message=f"📂 Executing step '{asset_name}' using {agent_name} agent...",
                        artefact_id=None,
                        agent_name="workflow",
                    )
                    self._notes.append(progress_note)
                    _logger.info(f"Added progress note for asset {asset_name}")

                # Prepare messages with context
                agent_messages = self._prepare_agent_messages(
                    messages, inputs, asset_config
                )

                # Execute agent
                _logger.info(f"Calling agent '{agent_name}' for asset '{asset_name}' (working_dir={self._working_dir})")
                try:
                    result = await agent.query(agent_messages, env_path=self._env_path, working_dir=self._working_dir)
                except Exception as e:
                    _logger.error(f"Agent '{agent_name}' failed with exception: {e}")
                    raise
                _logger.info(f"Agent '{agent_name}' returned result (length={len(str(result))})")
                result_string = str(result)

                # Check if execution paused for user input
                if "<taskpaused/>" in result_string:
                    _logger.info(f"Execution paused at asset '{asset_name}' for user input")

                    # Extract the question from the result
                    question = self._extract_question_from_result(result_string)

                    # Create paused execution state
                    if not self._stream_id:
                        raise ValueError("Cannot pause execution without stream_id")

                    if not self._original_messages:
                        raise ValueError("Cannot pause execution without original_messages")

                    state = PausedExecutionState(
                        stream_id=self._stream_id,
                        original_messages=self._original_messages,
                        yaml_plan=self.yaml_plan,
                        completed_assets=self.asset_results.copy(),
                        current_asset=asset_name,
                        next_asset_index=self._execution_order.index(asset_name),
                        question_asked=question,
                        user_input_messages=agent_messages,
                        notes=self._notes,
                    )

                    # Raise exception to pause execution
                    raise PausedExecutionException(state)

                # Extract artifact types from result
                actual_types = self.extract_artifact_types(result_string)

                # Validate type compatibility with planning
                self._validate_type_compatibility(asset_name, actual_types, asset_config)

                # Store result string for access by dependent assets
                self.asset_results[asset_name] = result_string

                # Log artifact production details
                self._log_artifact_production(asset_name, agent_name, result_string)

                # Validate the artifact if validation is enabled
                if self._validation_agent and self._original_goal:
                    validation_result = await self._validate_artifact(
                        asset_name=asset_name,
                        result_string=result_string,
                        asset_config=asset_config,
                        inputs=inputs,  # Pass input artifacts for context
                    )

                    if not validation_result.is_valid:
                        # Log the artifact content for debugging
                        artifact_preview = result_string[:1000] + "..." if len(result_string) > 1000 else result_string
                        _logger.warning(f"Validation failed artifact content for {asset_name}:\n{artifact_preview}")

                        # IMPORTANT: Save the failed asset result before removing it
                        # We need it for building replan context with artifact metadata
                        failed_result = result_string

                        # Remove the failed asset from results before replanning
                        # Otherwise the invalid result gets cached and reused!
                        valid_results = {k: v for k, v in self.asset_results.items() if k != asset_name}
                        _logger.info(f"Excluding failed asset '{asset_name}' from cached results for replan")

                        # Skip replanning if we're inside a loop body
                        if self._disable_validation_replan:
                            _logger.warning(
                                f"Validation failed for {asset_name} but replanning disabled (loop context): {validation_result.reason}"
                            )
                            # Continue execution - loop will handle validation
                        elif validation_result.should_ask_user:
                            if self._disable_user_prompts:
                                # User prompts disabled - go straight to replanning
                                _logger.warning(
                                    f"Validation failed for {asset_name}, user prompts disabled, replanning: {validation_result.reason}"
                                )
                                raise ReplanRequiredException(
                                    validation_result, valid_results, failed_result
                                )
                            else:
                                # Need user decision
                                _logger.warning(
                                    f"Validation failed for {asset_name}, asking user: {validation_result.reason}"
                                )
                                raise UserDecisionRequiredException(
                                    validation_result, valid_results
                                )
                        elif validation_result.should_replan:
                            # Trigger replanning
                            _logger.warning(
                                f"Validation failed for {asset_name}, replanning: {validation_result.reason}"
                            )
                            raise ReplanRequiredException(
                                validation_result, valid_results, failed_result
                            )
                        else:
                            # Low confidence but not low enough to ask user
                            _logger.warning(
                                f"Validation warning for {asset_name}: {validation_result.reason}"
                            )

                # Add completion note
                if self._notes is not None:
                    from yaaaf.components.data_types import Note

                    # Extract artifact references from the result string
                    artifact_refs = re.findall(r'<artefact[^>]*>[^<]+</artefact>', result_string)

                    if artifact_refs:
                        artifacts_display = " ".join(artifact_refs)
                        completion_note = Note(
                            message=f"✅ Completed '{asset_name}': produced {artifacts_display}",
                            artefact_id=None,
                            agent_name="workflow",
                        )
                    else:
                        # Fallback to types if no artifact references found
                        completion_note = Note(
                            message=f"✅ Completed '{asset_name}': produced {actual_types}",
                            artefact_id=None,
                            agent_name="workflow",
                        )

                    self._notes.append(completion_note)
                    _logger.info(f"Added completion note for asset {asset_name}")

            except PausedExecutionException:
                # This is expected behavior - just re-raise without logging as error
                raise
            except (ReplanRequiredException, UserDecisionRequiredException):
                # These are validation-triggered exceptions - re-raise
                raise
            except Exception as e:
                _logger.error(f"Failed to execute asset {asset_name}: {e}")
                raise

        # Return final result as a simple artifact for compatibility
        final_result = self.get_final_result()
        final_types = self.extract_artifact_types(final_result)
        
        return Artefact(
            type=final_types[0] if final_types else Artefact.Types.TEXT,
            code=final_result,
            description="Final workflow result",
        )

    async def _execute_loop(
        self, loop_name: str, loop_config: Dict, messages: Messages
    ) -> None:
        """Execute a loop node.

        Args:
            loop_name: Name of the loop asset
            loop_config: Loop configuration dict
            messages: Original messages for context
        """
        _logger.info(f"Starting loop '{loop_name}' (max_iterations={loop_config.get('max_iterations', 10)})")

        # Parse loop configuration
        try:
            loop_cfg = LoopConfig(**loop_config)
        except Exception as e:
            error_msg = f"Invalid loop configuration for '{loop_name}': {e}"
            _logger.error(error_msg)
            raise ValueError(error_msg)

        # Get loop inputs from outside the loop
        loop_inputs = self._gather_inputs(loop_cfg.inputs or [])

        # Track iteration results
        iteration_results: List[LoopIterationResult] = []
        previous_iteration_assets: Dict[str, str] = {}

        # Execute loop iterations
        for iteration in range(loop_cfg.max_iterations):
            _logger.info(f"Loop '{loop_name}' iteration {iteration + 1}/{loop_cfg.max_iterations}")

            # Add progress note
            if self._notes is not None:
                from yaaaf.components.data_types import Note
                note = Note(
                    message=f"🔁 Loop '{loop_name}' - iteration {iteration + 1}",
                    artefact_id=None,
                    agent_name="workflow",
                )
                self._notes.append(note)

            # Execute loop body (it's a sub-workflow)
            iteration_assets, validation_results = await self._execute_loop_body(
                loop_name=loop_name,
                loop_body=loop_cfg.loop_body,
                iteration=iteration,
                loop_inputs=loop_inputs,
                previous_iteration=previous_iteration_assets,
                messages=messages,
            )

            # Check if all assets are valid
            all_valid = all(validation_results.values())

            # Evaluate exit condition
            exit_condition_met = self._evaluate_loop_exit_condition(
                exit_condition=loop_cfg.exit_condition,
                iteration_assets=iteration_assets,
                validation_results=validation_results,
            )

            # Store iteration result
            iter_result = LoopIterationResult(
                iteration=iteration,
                assets=iteration_assets,
                all_valid=all_valid,
                validation_results=validation_results,
                exit_condition_met=exit_condition_met,
            )
            iteration_results.append(iter_result)

            # Update previous iteration for next loop
            previous_iteration_assets = iteration_assets

            # Check if we should exit
            if exit_condition_met:
                _logger.info(f"Loop '{loop_name}' exit condition met after {iteration + 1} iteration(s)")
                if self._notes is not None:
                    from yaaaf.components.data_types import Note
                    note = Note(
                        message=f"✅ Loop '{loop_name}' completed successfully after {iteration + 1} iteration(s)",
                        artefact_id=None,
                        agent_name="workflow",
                    )
                    self._notes.append(note)
                break
        else:
            # Max iterations reached without exit condition
            _logger.warning(
                f"Loop '{loop_name}' reached max_iterations ({loop_cfg.max_iterations}) "
                "without meeting exit condition"
            )
            if self._notes is not None:
                from yaaaf.components.data_types import Note
                note = Note(
                    message=f"⚠️ Loop '{loop_name}' stopped after {loop_cfg.max_iterations} iterations (max reached)",
                    artefact_id=None,
                    agent_name="workflow",
                )
                self._notes.append(note)

        # Return the specified loop output from the final iteration
        if not iteration_results:
            raise ValueError(f"Loop '{loop_name}' produced no iterations")

        final_iteration = iteration_results[-1]
        output_asset_name = loop_cfg.loop_output

        if output_asset_name not in final_iteration.assets:
            raise ValueError(
                f"Loop output asset '{output_asset_name}' not found in loop body. "
                f"Available: {list(final_iteration.assets.keys())}"
            )

        # Store the final loop result in asset_results
        final_result = final_iteration.assets[output_asset_name]
        self.asset_results[loop_name] = final_result

        _logger.info(f"Loop '{loop_name}' completed. Returning output from '{output_asset_name}'")

    def _load_external_artifact(self, asset_name: str, asset_config: Dict) -> None:
        """Load an external artifact from a prior plan execution.

        Args:
            asset_name: Name of the asset node
            asset_config: Asset configuration containing external_artifact_id
        """
        external_id = asset_config["external_artifact_id"]
        artifact_type = asset_config.get("type", "text")
        description = asset_config.get("description", f"External artifact {asset_name}")

        _logger.info(f"Loading external artifact '{asset_name}' with id={external_id[:12]}...")

        # Check if artifact exists in storage
        try:
            artifact = self.artefact_storage.retrieve_from_id(external_id)
            _logger.info(f"Successfully retrieved external artifact {external_id[:12]} from storage")

            # Format as result string (same format as agents produce)
            from yaaaf.components.agents.settings import task_completed_tag
            result_string = f"Loaded artifact from prior plan: <artefact type='{artifact_type}'>{external_id}</artefact> {task_completed_tag}"

            # Store in asset results
            self.asset_results[asset_name] = result_string

            # Add note
            if self._notes is not None:
                from yaaaf.components.data_types import Note
                note = Note(
                    message=f"🔗 Loaded external artifact '{asset_name}' from prior plan",
                    artefact_id=external_id,
                    agent_name="workflow",
                )
                self._notes.append(note)

        except Exception as e:
            error_msg = f"Failed to load external artifact {external_id}: {e}"
            _logger.error(error_msg)
            raise ValueError(error_msg)

    async def _execute_loop_body(
        self,
        loop_name: str,
        loop_body: Dict,
        iteration: int,
        loop_inputs: Dict[str, str],
        previous_iteration: Dict[str, str],
        messages: Messages,
    ) -> tuple[Dict[str, str], Dict[str, bool]]:
        """Execute one iteration of a loop body.

        Args:
            loop_name: Name of the parent loop
            loop_body: Loop body configuration (contains 'assets')
            iteration: Current iteration number (0-based)
            loop_inputs: Inputs from outside the loop
            previous_iteration: Asset results from previous iteration
            messages: Original messages

        Returns:
            Tuple of (iteration_assets, validation_results)
        """
        if "assets" not in loop_body:
            raise ValueError(f"Loop '{loop_name}' body must have 'assets' section")

        # Create a sub-executor for this iteration
        # Build a mini YAML plan for the loop body
        import yaml
        loop_body_yaml = yaml.dump(loop_body)

        _logger.debug(f"Loop '{loop_name}' iteration {iteration} body:\n{loop_body_yaml}")

        # Create sub-executor with special context
        # Note: We create a fresh executor per iteration to isolate state
        # IMPORTANT: disable_validation_replan=True prevents validation failures from
        # triggering replanning within loop bodies - the loop handles validation itself
        sub_executor = WorkflowExecutor(
            yaml_plan=loop_body_yaml,
            agents=self.agents,
            notes=self._notes,
            stream_id=self._stream_id,
            validation_agent=self._validation_agent,
            original_goal=self._original_goal,
            disable_user_prompts=self._disable_user_prompts,
            env_path=self._env_path,
            working_dir=self._working_dir,
            disable_validation_replan=True,  # Loop handles validation, don't replan
        )

        # Inject special loop variables into the sub-executor's context
        # __loop_input__: inputs from outside the loop
        for input_name, input_value in loop_inputs.items():
            sub_executor.asset_results[f"__loop_input__{input_name}"] = input_value

        # __previous_iteration__: results from last iteration
        for asset_name, asset_value in previous_iteration.items():
            sub_executor.asset_results[f"__previous__{asset_name}"] = asset_value

        # __iteration__: current iteration number
        sub_executor.asset_results["__iteration__"] = str(iteration)

        # Execute the loop body
        try:
            await sub_executor.execute(messages)
        except Exception as e:
            _logger.error(f"Loop '{loop_name}' iteration {iteration} failed: {e}")
            raise

        # Get results from this iteration
        iteration_assets = sub_executor.get_completed_assets()

        # Validate each asset in the iteration
        validation_results = {}
        loop_body_assets = loop_body.get("assets", {})

        for asset_name, result_string in iteration_assets.items():
            # Skip special variables
            if asset_name.startswith("__"):
                continue

            # Get asset config for validation
            asset_config = loop_body_assets.get(asset_name, {})

            # Use ValidationAgent if available for semantic validation
            if self._validation_agent and self._original_goal:
                try:
                    # Get inputs for this asset from the loop body config
                    input_names = asset_config.get("inputs", [])
                    inputs = {}
                    for input_name in input_names:
                        # Check if input is from current iteration
                        if input_name in iteration_assets:
                            inputs[input_name] = iteration_assets[input_name]
                        # Check if input is from previous iteration
                        elif f"__previous__{input_name}" in iteration_assets:
                            inputs[input_name] = iteration_assets[f"__previous__{input_name}"]
                        # Check if input is from loop input
                        elif f"__loop_input__{input_name}" in iteration_assets:
                            inputs[input_name] = iteration_assets[f"__loop_input__{input_name}"]

                    _logger.debug(f"Validating loop iteration asset '{asset_name}' (iteration {iteration})")

                    validation_result = await self._validate_artifact(
                        asset_name=asset_name,
                        result_string=result_string,
                        asset_config=asset_config,
                        inputs=inputs,
                    )

                    is_valid = validation_result.is_valid

                    _logger.debug(
                        f"Loop iteration {iteration} validation for '{asset_name}': "
                        f"valid={is_valid}, confidence={validation_result.confidence:.2f}, "
                        f"reason={validation_result.reason[:100] if validation_result.reason else 'N/A'}"
                    )

                except Exception as e:
                    # If validation fails, log error and fall back to simple check
                    _logger.warning(f"ValidationAgent failed for loop asset '{asset_name}': {e}")
                    is_valid = bool(result_string and result_string.strip())
            else:
                # No validation agent - use simple non-empty check
                is_valid = bool(result_string and result_string.strip())

            validation_results[asset_name] = is_valid

        return iteration_assets, validation_results

    def _evaluate_loop_exit_condition(
        self,
        exit_condition: LoopExitCondition,
        iteration_assets: Dict[str, str],
        validation_results: Dict[str, bool],
    ) -> bool:
        """Evaluate whether the loop should exit.

        Args:
            exit_condition: Exit condition configuration
            iteration_assets: Assets produced in this iteration
            validation_results: Validation status for each asset

        Returns:
            True if loop should exit, False to continue
        """
        condition_type = exit_condition.type

        if condition_type == ExitConditionType.ALL_VALID:
            # All assets must be valid
            # Filter to specified assets if provided
            assets_to_check = exit_condition.assets
            if assets_to_check:
                results_to_check = {
                    name: validation_results[name]
                    for name in assets_to_check
                    if name in validation_results
                }
            else:
                results_to_check = validation_results

            return all(results_to_check.values()) if results_to_check else False

        elif condition_type == ExitConditionType.ANY_VALID:
            # At least one specified asset must be valid
            assets_to_check = exit_condition.assets or []
            results_to_check = {
                name: validation_results.get(name, False)
                for name in assets_to_check
            }
            return any(results_to_check.values()) if results_to_check else False

        elif condition_type == ExitConditionType.CUSTOM:
            # Evaluate custom condition (future enhancement)
            condition_expr = exit_condition.condition or ""
            _logger.warning(
                f"Custom loop exit conditions not yet implemented. "
                f"Condition: '{condition_expr}'"
            )
            return False

        else:
            _logger.warning(f"Unknown exit condition type: {condition_type}")
            return False

    def _log_artifact_production(self, asset_name: str, agent_name: str, result_string: str) -> None:
        """Log details about artifacts produced by an agent at a specific step.

        Args:
            asset_name: Name of the workflow step
            agent_name: Name of the agent that produced the artifacts
            result_string: Agent output containing artifact references
        """
        step_number = self._execution_order.index(asset_name) + 1
        total_steps = len(self._execution_order)
        artifact_matches = re.findall(r"<artefact type='([^']+)'>([^<]+)</artefact>", result_string)

        if artifact_matches:
            for art_type, art_id in artifact_matches:
                _logger.info(
                    f"[Step {step_number}/{total_steps}] Agent '{agent_name}' produced artifact: "
                    f"type={art_type}, id={art_id[:12]}..., step_name='{asset_name}'"
                )
        else:
            _logger.info(
                f"[Step {step_number}/{total_steps}] Agent '{agent_name}' completed step '{asset_name}' "
                f"(no artifacts found in output)"
            )

    def _evaluate_conditions(self, asset_name: str, asset_config: Dict) -> bool:
        """Evaluate conditions for an asset."""
        conditions = asset_config.get("conditions", [])

        for condition in conditions:
            if "if" in condition:
                # Parse condition like "sales_data.row_count > 100"
                try:
                    if not self._evaluate_single_condition(condition["if"]):
                        return False
                except Exception as e:
                    _logger.warning(f"Failed to evaluate condition: {e}")
                    return True  # Continue on error

        return True

    def _evaluate_single_condition(self, condition_str: str) -> bool:
        """Evaluate a single condition expression."""
        # Parse expressions like "asset_name.property > value"
        match = re.match(r"(\w+)\.(\w+)\s*([<>=]+)\s*(\d+)", condition_str)
        if not match:
            return True  # Can't parse, assume true

        asset_name, property_name, operator, value = match.groups()
        value = int(value)

        # Check if we have the asset result
        if asset_name not in self.asset_results:
            return True  # Asset not available yet

        # For now, skip property validation since we only have result strings
        # TODO: Implement property validation on result strings if needed
        return True

        # For now, skip detailed property validation since we only have result strings
        # TODO: Implement property validation on result strings if needed
        return True

    def _gather_inputs(self, input_names: List[str]) -> Dict[str, str]:
        """Gather input result strings for an agent."""
        inputs = {}
        for input_name in input_names:
            if input_name in self.asset_results:
                inputs[input_name] = self.asset_results[input_name]
            else:
                _logger.warning(f"Input {input_name} not found")
        return inputs

    def _prepare_agent_messages(
        self, messages: Messages, inputs: Dict[str, str], asset_config: Dict
    ) -> Messages:
        """Prepare messages for agent execution.

        Only includes user messages from original context to prevent artifact
        confusion. DAG input artifacts are added as assistant utterances so
        agents receive exactly the artifacts specified in their inputs.
        """
        # Only copy USER messages from original - exclude assistant messages
        # to prevent agents from seeing artifacts from unrelated workflow steps
        user_utterances = [
            u for u in messages.utterances if u.role == "user"
        ]
        agent_messages = Messages(utterances=user_utterances.copy())

        # Add input results as assistant utterances so agents can extract artifacts naturally
        # These are the ONLY artifacts the agent should see (from its DAG inputs)
        if inputs:
            # Calculate the starting index for assistant messages (after user messages)
            start_idx = len(agent_messages.utterances)
            for idx, (input_name, result_string) in enumerate(inputs.items()):
                msg_idx = start_idx + idx
                # Extract artifact info for logging
                import re
                artifact_matches = re.findall(r"<artefact type='([^']+)'>([^<]+)</artefact>", result_string)
                if artifact_matches:
                    for art_type, art_id in artifact_matches:
                        _logger.info(f"DAG input #{msg_idx} '{input_name}' -> artifact type={art_type}, id={art_id[:8]}...")
                else:
                    _logger.info(f"DAG input #{msg_idx} '{input_name}' -> no artifacts found in result")

                agent_messages.utterances.append(
                    Utterance(
                        role="assistant",
                        content=result_string
                    )
                )

        # Add specific instruction from asset description
        if "description" in asset_config:
            agent_messages.utterances.append(
                Utterance(role="user", content=asset_config["description"])
            )

        return agent_messages

    def extract_artifact_types(self, result_string: str) -> List[str]:
        """Extract artifact types from agent result string.
        
        Agents return strings like: 'Operation completed. Result: <artefact type='table'>123456</artefact> <taskcompleted/>'
        This method extracts all artifact types found in the result.
        
        Returns:
            List of artifact types (e.g., ['TABLE', 'TEXT'])
        """
        import re
        matches = re.findall(r"<artefact type='([^']+)'>", str(result_string))
        if matches:
            return [match.upper() for match in matches]  # Convert to uppercase to match Artefact.Types
        return [Artefact.Types.TEXT]  # Default fallback

    def _validate_result(self, artifact: Artefact, asset_config: Dict) -> bool:
        """Validate artifact against asset configuration."""
        validations = asset_config.get("validation", [])

        for validation in validations:
            if isinstance(validation, str):
                # Parse validation like "row_count > 0"
                if "row_count" in validation and artifact.data is not None:
                    match = re.search(r"row_count\s*>\s*(\d+)", validation)
                    if match:
                        min_rows = int(match.group(1))
                        if len(artifact.data) <= min_rows:
                            return False
                elif "columns" in validation:
                    # Check required columns
                    pass  # TODO: Implement column validation

        return True

    def _validate_type_compatibility(self, asset_name: str, actual_types: List[str], asset_config: Dict) -> None:
        """Validate that the actual artifact types match what the next steps expect."""
        expected_type = asset_config.get("type", "TEXT").upper()

        # Normalize actual types to uppercase for comparison
        actual_types_upper = [t.upper() for t in actual_types]

        # Check if any of the actual types match the expected type
        type_match = expected_type in actual_types_upper
        
        if not type_match:
            _logger.warning(
                f"Type mismatch for asset '{asset_name}': "
                f"planned for {expected_type}, but agent produced {actual_types}"
            )
            
            # Check if any dependent assets expect the planned type
            dependent_assets = self._find_dependent_assets(asset_name)
            if dependent_assets:
                _logger.warning(
                    f"Asset '{asset_name}' type mismatch may affect dependent assets: {dependent_assets}"
                )
        else:
            _logger.info(
                f"Type validation passed for asset '{asset_name}': "
                f"expected {expected_type}, found in {actual_types}"
            )
    
    def _find_dependent_assets(self, asset_name: str) -> List[str]:
        """Find assets that depend on the given asset."""
        dependents = []
        for name, config in self.plan.get("assets", {}).items():
            inputs = config.get("inputs", [])
            if asset_name in inputs:
                dependents.append(name)
        return dependents
    
    def _validate_workflow_type_compatibility(self) -> None:
        """Validate type compatibility across the entire workflow during planning."""
        from yaaaf.components.data_types import AGENT_ARTIFACT_SPECS
        
        for asset_name in self._execution_order:
            asset_config = self.plan["assets"][asset_name]
            agent_name = asset_config.get("agent")
            planned_type = asset_config.get("type", "TEXT").upper()
            inputs = asset_config.get("inputs", [])
            
            # Check if agent can actually produce the planned type
            if agent_name in AGENT_ARTIFACT_SPECS:
                agent_spec = AGENT_ARTIFACT_SPECS[agent_name]
                agent_produces = [t.value.upper() for t in agent_spec.produces]
                
                if planned_type not in agent_produces:
                    _logger.warning(
                        f"Planning mismatch for asset '{asset_name}': "
                        f"agent '{agent_name}' produces {agent_produces} but plan expects {planned_type}"
                    )
            
            # Check input type compatibility
            if inputs:
                for input_asset in inputs:
                    if input_asset in self.plan["assets"]:
                        input_type = self.plan["assets"][input_asset].get("type", "TEXT").upper()
                        
                        # Check if current agent can accept the input type
                        if agent_name in AGENT_ARTIFACT_SPECS:
                            agent_spec = AGENT_ARTIFACT_SPECS[agent_name]
                            if agent_spec.accepts:  # None means source agent
                                agent_accepts = [t.value.upper() for t in agent_spec.accepts]
                                if input_type not in agent_accepts:
                                    _logger.warning(
                                        f"Input type mismatch for asset '{asset_name}': "
                                        f"agent '{agent_name}' accepts {agent_accepts} but input '{input_asset}' produces {input_type}"
                                    )
    
    def _validate_plan_agent_types(self) -> None:
        """Validate that the plan uses the correct types for each agent."""
        from yaaaf.components.data_types import AGENT_ARTIFACT_SPECS
        
        errors = []
        
        for asset_name in self._execution_order:
            asset_config = self.plan["assets"][asset_name]
            agent_name = asset_config.get("agent")
            planned_type = asset_config.get("type", "TEXT").lower()
            
            # Check if agent spec exists
            if agent_name in AGENT_ARTIFACT_SPECS:
                agent_spec = AGENT_ARTIFACT_SPECS[agent_name]
                agent_produces = [t.value.lower() for t in agent_spec.produces]
                
                if planned_type not in agent_produces:
                    errors.append(
                        f"Asset '{asset_name}' uses agent '{agent_name}' with type '{planned_type}', "
                        f"but agent only produces: {agent_produces}"
                    )
        
        if errors:
            error_msg = "Plan validation failed:\n" + "\n".join(f"- {err}" for err in errors)
            raise ValueError(error_msg)

    def get_final_result(self) -> str:
        """Get the final result string from the workflow."""
        if not self._execution_order:
            raise ValueError("No assets executed")

        # Return the last executed asset's result
        last_asset = self._execution_order[-1]
        if last_asset in self.asset_results:
            return self.asset_results[last_asset]

        # Find the last available result
        for asset_name in reversed(self._execution_order):
            if asset_name in self.asset_results:
                return self.asset_results[asset_name]

        raise ValueError("No results produced")

    def get_completed_assets(self) -> Dict[str, str]:
        """Get all completed asset results."""
        return self.asset_results.copy()

    def build_replan_context(
        self,
        validation_result: ValidationResult,
        completed_assets: Dict[str, str],
        iteration: int = 1,
        failed_asset_result: str = "",
    ) -> ReplanContext:
        """Build a ReplanContext from validation failure.

        Args:
            validation_result: The validation result that triggered replanning
            completed_assets: Dict of completed asset names to their result strings
            iteration: Which replan attempt this is (1 = first replan)
            failed_asset_result: Result string of the failed asset (for metadata extraction)

        Returns:
            ReplanContext for the planner
        """
        if not validation_result.failure_type or not validation_result.failure_details:
            # If validation didn't provide failure details, create default
            failure_type = FailureType.VALIDATION_ERROR
            failure_details = FailureDetails(
                raw_output=validation_result.reason,
                error_message=validation_result.reason,
            )
        else:
            failure_type = validation_result.failure_type
            failure_details = validation_result.failure_details

        # Build metadata for completed artifacts
        completed_metadata = []
        for asset_name, result_string in completed_assets.items():
            artifact_meta = self._build_artifact_metadata(asset_name, result_string)
            if artifact_meta:
                completed_metadata.append(artifact_meta)

        # Build metadata for failed artifact
        failed_asset_name = validation_result.asset_name
        # Use the passed failed_asset_result instead of trying to get from asset_results
        # (it was removed to prevent caching)
        failed_metadata = self._build_artifact_metadata(failed_asset_name, failed_asset_result)

        if not failed_metadata:
            # Fallback if we can't build metadata
            failed_metadata = ArtifactMetadata(
                id="unknown",
                type="text",
                name=failed_asset_name or "unknown",
                description=f"Failed step: {failed_asset_name}",
                size_bytes=len(failed_asset_result),
                agent_name="unknown",
            )

        # Create failure summary
        failure_summary = create_failure_summary(failure_type, failure_details)

        return ReplanContext(
            original_goal=self._original_goal or "Complete the task",
            iteration=iteration,
            prior_plan_id=str(id(self)),  # Use object id as plan identifier (convert to string)
            completed_artifacts=completed_metadata,
            failed_artifact=failed_metadata,
            failure_type=failure_type,
            failure_summary=failure_summary,
            failure_details=failure_details,
        )

    def _build_artifact_metadata(
        self, asset_name: str, result_string: str
    ) -> Optional[ArtifactMetadata]:
        """Build ArtifactMetadata from an asset result.

        Args:
            asset_name: Name of the asset
            result_string: Result string containing artifact reference

        Returns:
            ArtifactMetadata or None if no artifact found
        """
        # Extract artifact info from result string
        match = re.search(r"<artefact type='([^']+)'>([^<]+)</artefact>", result_string)
        if not match:
            return None

        artifact_type, artifact_id = match.groups()

        # Get asset config to find agent name
        asset_config = self.plan["assets"].get(asset_name, {})
        agent_name = asset_config.get("agent", "unknown")
        description = asset_config.get("description", f"Step {asset_name}")

        # Try to get artifact from storage to get accurate size
        size_bytes = len(result_string)  # Default to result string size
        try:
            artifact = self.artefact_storage.retrieve_from_id(artifact_id)
            if artifact.code:
                size_bytes = len(artifact.code)
            elif artifact.data is not None:
                size_bytes = len(str(artifact.data))
        except Exception:
            pass  # Use default size

        return ArtifactMetadata(
            id=artifact_id,
            type=artifact_type,
            name=asset_name,
            description=description,
            size_bytes=size_bytes,
            agent_name=agent_name,
        )

    async def _validate_artifact(
        self, asset_name: str, result_string: str, asset_config: Dict, inputs: Dict[str, str] = None
    ) -> ValidationResult:
        """Validate an artifact produced by an agent.

        Args:
            asset_name: Name of the asset being validated
            result_string: Agent result string containing artifact
            asset_config: Asset configuration from the plan
            inputs: Dict of input asset names to their result strings (context for validation)

        Returns:
            ValidationResult with validation status and recommendations
        """
        if not self._validation_agent or not self._original_goal:
            # Validation not enabled - return valid
            return ValidationResult.valid(asset_name=asset_name)

        step_description = asset_config.get("description", f"Execute {asset_name}")
        expected_type = asset_config.get("type", "TEXT")
        agent_name = asset_config.get("agent", "unknown")

        _logger.info(f"Validating artifact for asset '{asset_name}' (agent={agent_name}) with {len(inputs) if inputs else 0} input artifacts")

        try:
            result = await self._validation_agent.validate_from_result_string(
                result_string=result_string,
                user_goal=self._original_goal,
                step_description=step_description,
                expected_type=expected_type,
                asset_name=asset_name,
                input_artifacts=inputs,
                agent_name=agent_name,
            )

            _logger.info(
                f"Validation result for '{asset_name}': "
                f"valid={result.is_valid}, confidence={result.confidence}, "
                f"reason={result.reason}"
            )

            return result

        except Exception as e:
            _logger.error(f"Validation failed for '{asset_name}': {e}")
            # Return valid on error to not block execution
            return ValidationResult.valid(
                reason=f"Validation skipped due to error: {e}",
                asset_name=asset_name,
            )

    def _extract_question_from_result(self, result_string: str) -> str:
        """Extract the user question from a paused result.

        Looks for text between ```question and ``` markers, or
        returns the full result if no question markers found.

        Args:
            result_string: The result string containing the question

        Returns:
            The extracted question text
        """
        # Try to extract from ```question block
        question_match = re.search(
            r"```question\s*(.*?)```", result_string, re.DOTALL
        )
        if question_match:
            return question_match.group(1).strip()

        # Fallback: extract everything before <taskpaused/>
        paused_index = result_string.find("<taskpaused/>")
        if paused_index > 0:
            # Get everything before the pause tag
            question = result_string[:paused_index].strip()
            # Remove any "Question for user:" prefix
            question = re.sub(r"^Question for user:\s*", "", question, flags=re.IGNORECASE)
            return question

        # Last resort: return full result
        return result_string.strip()

    async def resume_from_paused_state(
        self, state: PausedExecutionState, user_response: str
    ) -> Artefact:
        """Resume execution from a paused state with user's response.

        Args:
            state: The paused execution state
            user_response: The user's response to the question

        Returns:
            Final artifact produced by the workflow
        """
        _logger.info(
            f"Resuming execution for stream {state.stream_id} "
            f"from asset '{state.current_asset}' with user response"
        )

        # Step 1: Use the user's response directly as the result
        # Don't call the UserInputAgent again - it's designed to ask questions, not extract answers
        # The user has provided their answer, so we just use it directly
        _logger.info(f"Using user response directly: {user_response[:100]}")

        # Create a proper artifact for the user's response so downstream agents can extract it
        # Include both the question and response for full context
        from yaaaf.components.agents.settings import task_completed_tag
        from yaaaf.components.agents.hash_utils import create_hash

        question = state.question_asked or "unknown question"
        artifact_content = f'When queried "{question}" the user replied "{user_response}"'

        artifact_id = create_hash(f"user_input_{artifact_content}")
        user_artifact = Artefact(
            id=artifact_id,
            type="text",
            code=artifact_content,
            description="User input with question context"
        )
        self.artefact_storage.store_artefact(artifact_id, user_artifact)

        # Format with proper artifact wrapper so downstream agents can extract it
        final_result_string = f"User provided input: <artefact type='text'>{artifact_id}</artefact> {task_completed_tag}"

        _logger.info(f"User input completed with artifact {artifact_id}: {user_response[:100]}")

        # Step 2: Restore completed assets and add the user input result
        self.asset_results = state.completed_assets.copy()
        self.asset_results[state.current_asset] = final_result_string

        # Add completion note for user input step
        if self._notes is not None:
            from yaaaf.components.data_types import Note

            completion_note = Note(
                message=f"✅ User provided input: {user_response[:200]}{'...' if len(user_response) > 200 else ''}",
                artefact_id=artifact_id,
                agent_name="workflow",
            )
            self._notes.append(completion_note)

        # Step 3: Continue execution from the next asset
        _logger.info(
            f"Continuing execution from asset index {state.next_asset_index + 1}"
        )

        for i in range(state.next_asset_index + 1, len(self._execution_order)):
            asset_name = self._execution_order[i]
            asset_config = self.plan["assets"][asset_name]

            # Check if asset is already cached (from previous execution)
            if asset_name in self.asset_results:
                _logger.info(f"Reusing cached result for asset '{asset_name}'")
                if self._notes is not None:
                    from yaaaf.components.data_types import Note
                    reuse_note = Note(
                        message=f"♻️ Reusing cached result for '{asset_name}'",
                        artefact_id=None,
                        agent_name="workflow",
                    )
                    self._notes.append(reuse_note)
                continue

            # Check conditions
            if not self._evaluate_conditions(asset_name, asset_config):
                _logger.info(f"Skipping {asset_name} due to conditions")
                continue

            # Gather input artifacts
            inputs = self._gather_inputs(asset_config.get("inputs", []))

            # Execute agent
            try:
                agent_name = asset_config["agent"]
                if agent_name not in self.agents:
                    raise ValueError(f"Agent {agent_name} not found")

                agent = self.agents[agent_name]

                # Update stream status
                if self._stream_id:
                    from yaaaf.server.accessories import _stream_id_to_status

                    if self._stream_id in _stream_id_to_status:
                        _stream_id_to_status[self._stream_id].current_agent = (
                            asset_config.get("description", f"Executing {asset_name}")
                        )
                        _stream_id_to_status[self._stream_id].goal = f"Step: {asset_name}"

                # Add progress note
                if self._notes is not None:
                    from yaaaf.components.data_types import Note

                    progress_note = Note(
                        message=f"📂 Executing step '{asset_name}' using {agent_name} agent...",
                        artefact_id=None,
                        agent_name="workflow",
                    )
                    self._notes.append(progress_note)

                # Prepare messages with context
                agent_messages = self._prepare_agent_messages(
                    state.original_messages, inputs, asset_config
                )

                # Execute agent
                _logger.info(f"Calling agent '{agent_name}' for resumed asset '{asset_name}'")
                try:
                    result = await agent.query(agent_messages, env_path=self._env_path, working_dir=self._working_dir)
                except Exception as e:
                    _logger.error(f"Agent '{agent_name}' failed with exception: {e}")
                    raise
                _logger.info(f"Agent '{agent_name}' returned result (length={len(str(result))})")
                result_string = str(result)

                # Check for another pause (nested user input)
                if "<taskpaused/>" in result_string:
                    _logger.warning("Nested user input detected - raising pause again")
                    question = self._extract_question_from_result(result_string)

                    nested_state = PausedExecutionState(
                        stream_id=state.stream_id,
                        original_messages=state.original_messages,
                        yaml_plan=self.yaml_plan,
                        completed_assets=self.asset_results.copy(),
                        current_asset=asset_name,
                        next_asset_index=i,
                        question_asked=question,
                        user_input_messages=agent_messages,
                        notes=self._notes,
                    )
                    raise PausedExecutionException(nested_state)

                # Extract artifact types from result
                actual_types = self.extract_artifact_types(result_string)

                # Validate type compatibility with planning
                self._validate_type_compatibility(
                    asset_name, actual_types, asset_config
                )

                # Store result string for access by dependent assets
                self.asset_results[asset_name] = result_string

                # Log artifact production details
                self._log_artifact_production(asset_name, agent_name, result_string)

                # Add completion note
                if self._notes is not None:
                    from yaaaf.components.data_types import Note

                    # Extract artifact references from the result string
                    artifact_refs = re.findall(
                        r"<artefact[^>]*>[^<]+</artefact>", result_string
                    )

                    if artifact_refs:
                        artifacts_display = " ".join(artifact_refs)
                        completion_note = Note(
                            message=f"✅ Completed '{asset_name}': produced {artifacts_display}",
                            artefact_id=None,
                            agent_name="workflow",
                        )
                    else:
                        completion_note = Note(
                            message=f"✅ Completed '{asset_name}': produced {actual_types}",
                            artefact_id=None,
                            agent_name="workflow",
                        )

                    self._notes.append(completion_note)

            except PausedExecutionException:
                # This is expected behavior (nested pause) - just re-raise without logging as error
                raise
            except Exception as e:
                _logger.error(f"Failed to execute asset {asset_name}: {e}")
                raise

        # Return final result
        final_result = self.get_final_result()
        final_types = self.extract_artifact_types(final_result)

        return Artefact(
            type=final_types[0] if final_types else Artefact.Types.TEXT,
            code=final_result,
            description="Final workflow result",
        )
