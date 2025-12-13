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

    def __init__(self, validation_result: ValidationResult, completed_assets: Dict[str, str]):
        self.validation_result = validation_result
        self.completed_assets = completed_assets
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
        """
        self.yaml_plan = yaml_plan  # Store raw YAML for state persistence
        self.plan = yaml.safe_load(yaml_plan)
        self.agents = agents
        self.asset_results = {}  # Store result strings by asset name
        self.artefact_storage = ArtefactStorage()
        self._execution_order = []
        self._notes = notes if notes is not None else []
        self._stream_id = stream_id
        self._original_messages = original_messages
        self._validation_agent = validation_agent
        self._original_goal = original_goal
        self._build_execution_graph()

    def _build_execution_graph(self):
        """Build execution order from dependencies."""
        assets = self.plan.get("assets", {})

        # Build dependency graph
        dependencies = {}
        for asset_name, asset_config in assets.items():
            dependencies[asset_name] = asset_config.get("inputs", [])
            
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
                result = await agent.query(agent_messages)
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

                # Validate the artifact if validation is enabled
                if self._validation_agent and self._original_goal:
                    validation_result = await self._validate_artifact(
                        asset_name=asset_name,
                        result_string=result_string,
                        asset_config=asset_config,
                    )

                    if not validation_result.is_valid:
                        if validation_result.should_ask_user:
                            # Need user decision
                            _logger.warning(
                                f"Validation failed for {asset_name}, asking user: {validation_result.reason}"
                            )
                            raise UserDecisionRequiredException(
                                validation_result, self.asset_results.copy()
                            )
                        elif validation_result.should_replan:
                            # Trigger replanning
                            _logger.warning(
                                f"Validation failed for {asset_name}, replanning: {validation_result.reason}"
                            )
                            raise ReplanRequiredException(
                                validation_result, self.asset_results.copy()
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
        """Prepare messages for agent execution."""
        # Start with original messages
        agent_messages = Messages(utterances=messages.utterances.copy())

        # Add input results as assistant utterances so agents can extract artifacts naturally
        if inputs:
            for input_name, result_string in inputs.items():
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
        
        # Check if any of the actual types match the expected type
        type_match = expected_type in actual_types
        
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

    async def _validate_artifact(
        self, asset_name: str, result_string: str, asset_config: Dict
    ) -> ValidationResult:
        """Validate an artifact produced by an agent.

        Args:
            asset_name: Name of the asset being validated
            result_string: Agent result string containing artifact
            asset_config: Asset configuration from the plan

        Returns:
            ValidationResult with validation status and recommendations
        """
        if not self._validation_agent or not self._original_goal:
            # Validation not enabled - return valid
            return ValidationResult.valid(asset_name=asset_name)

        step_description = asset_config.get("description", f"Execute {asset_name}")
        expected_type = asset_config.get("type", "TEXT")

        _logger.info(f"Validating artifact for asset '{asset_name}'")

        try:
            result = await self._validation_agent.validate_from_result_string(
                result_string=result_string,
                user_goal=self._original_goal,
                step_description=step_description,
                expected_type=expected_type,
                asset_name=asset_name,
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

        # Format the user's response as the completed result with task completed tag
        from yaaaf.components.agents.settings import task_completed_tag
        final_result_string = f"User response: {user_response}\n\n{task_completed_tag}"

        _logger.info(f"User input completed with: {user_response}")

        # Step 2: Restore completed assets and add the user input result
        self.asset_results = state.completed_assets.copy()
        self.asset_results[state.current_asset] = final_result_string

        # Add completion note for user input step
        if self._notes is not None:
            from yaaaf.components.data_types import Note

            completion_note = Note(
                message=f"✅ User provided input: {user_response}",
                artefact_id=None,
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
                result = await agent.query(agent_messages)
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
