import logging
import yaml
import re
from typing import Dict, Any, List, Optional, Set
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage

_logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when asset validation fails."""

    pass


class ConditionError(Exception):
    """Raised when condition evaluation fails."""

    pass


class WorkflowExecutor:
    """Executes a YAML workflow plan by coordinating agents."""

    def __init__(self, yaml_plan: str, agents: Dict[str, Any], notes: List[Any] = None, stream_id: str = None):
        """Initialize workflow executor.

        Args:
            yaml_plan: YAML workflow definition
            agents: Dictionary mapping agent names to agent instances
            notes: Optional list to append execution progress notes
            stream_id: Optional stream ID for status updates
        """
        self.plan = yaml.safe_load(yaml_plan)
        self.agents = agents
        self.asset_artifacts = {}  # Store artifacts by asset name
        self.artefact_storage = ArtefactStorage()
        self._execution_order = []
        self._notes = notes if notes is not None else []
        self._stream_id = stream_id
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
                        _logger.info(f"Updated stream status to: {asset_config.get('description')}")
                
                # Add progress note
                if self._notes is not None:
                    from yaaaf.components.data_types import Note
                    progress_note = Note(
                        message=f"🔄 Executing step '{asset_name}' using {agent_name} agent...",
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

                # Extract artifact from result
                artifact = self._extract_artifact(result, asset_config)

                # Validate result
                if not self._validate_result(artifact, asset_config):
                    raise ValidationError(f"Asset {asset_name} failed validation")

                # Store artifact
                self.asset_artifacts[asset_name] = artifact
                
                # Add completion note with artifact info
                if self._notes is not None:
                    from yaaaf.components.data_types import Note
                    artifact_summary = artifact.summary or artifact.description or f"{artifact.type} artifact"
                    completion_note = Note(
                        message=f"✅ Completed '{asset_name}': {artifact_summary}",
                        artefact_id=artifact.id if artifact.id else None,
                        agent_name="workflow",
                    )
                    self._notes.append(completion_note)
                    _logger.info(f"Added completion note for asset {asset_name}")

            except Exception as e:
                _logger.error(f"Failed to execute asset {asset_name}: {e}")
                raise

        # Return final artifact
        return self._get_final_artifact()

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

        # Check if we have the asset
        if asset_name not in self.asset_artifacts:
            return True  # Asset not available yet

        artifact = self.asset_artifacts[asset_name]

        # Get property value (simplified for now)
        if property_name == "row_count" and hasattr(artifact, "data"):
            if artifact.data is not None:
                actual_value = len(artifact.data)
            else:
                return True
        else:
            return True  # Unknown property

        # Evaluate operator
        if operator == ">":
            return actual_value > value
        elif operator == "<":
            return actual_value < value
        elif operator == ">=":
            return actual_value >= value
        elif operator == "<=":
            return actual_value <= value
        elif operator == "==":
            return actual_value == value

        return True

    def _gather_inputs(self, input_names: List[str]) -> Dict[str, Artefact]:
        """Gather input artifacts for an agent."""
        inputs = {}
        for input_name in input_names:
            if input_name in self.asset_artifacts:
                inputs[input_name] = self.asset_artifacts[input_name]
            else:
                _logger.warning(f"Input {input_name} not found")
        return inputs

    def _prepare_agent_messages(
        self, messages: Messages, inputs: Dict[str, Artefact], asset_config: Dict
    ) -> Messages:
        """Prepare messages for agent execution."""
        # Start with original messages
        agent_messages = Messages(utterances=messages.utterances.copy())

        # Add input artifacts as context
        if inputs:
            context_parts = []
            artifact_refs = []
            for input_name, artifact in inputs.items():
                # Store artifact in storage so it can be retrieved by ID
                self.artefact_storage.store_artefact(artifact.id, artifact)
                
                # Create artifact reference
                artifact_refs.append(f"<artefact type='{artifact.type}'>{artifact.id}</artefact>")
                
                # Also add human-readable context
                if artifact.type == Artefact.Types.TABLE and artifact.data is not None:
                    context_parts.append(
                        f"Input {input_name} (table):\n{artifact.data.to_string()}"
                    )
                elif artifact.type == Artefact.Types.TEXT and artifact.code:
                    context_parts.append(f"Input {input_name} (text):\n{artifact.code}")
                elif artifact.summary:
                    context_parts.append(f"Input {input_name}: {artifact.summary}")

            if context_parts:
                # Add both artifact references and human-readable context
                context_message = "\n\n".join(context_parts)
                if artifact_refs:
                    artifact_refs_str = " ".join(artifact_refs)
                    context_message = f"Artifacts: {artifact_refs_str}\n\n{context_message}"
                
                agent_messages.utterances.append(
                    Utterance(
                        role="system",
                        content=f"Context from previous steps:\n{context_message}",
                    )
                )

        # Add specific instruction from asset description
        if "description" in asset_config:
            agent_messages.utterances.append(
                Utterance(role="user", content=asset_config["description"])
            )

        return agent_messages

    def _extract_artifact(self, agent_result: Any, asset_config: Dict) -> Artefact:
        """Extract artifact from agent result."""
        # Handle different result types
        if hasattr(agent_result, "artefacts") and agent_result.artefacts:
            # Agent returned artifacts
            return agent_result.artefacts[-1]  # Use last artifact
        elif hasattr(agent_result, "content"):
            # Text response
            return Artefact(
                type=asset_config.get("type", Artefact.Types.TEXT),
                code=agent_result.content,
                description=asset_config.get("description", ""),
            )
        else:
            # Unknown format
            return Artefact(
                type=asset_config.get("type", Artefact.Types.TEXT),
                code=str(agent_result),
                description=asset_config.get("description", ""),
            )

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

    def _get_final_artifact(self) -> Artefact:
        """Get the final artifact from the workflow."""
        if not self._execution_order:
            raise ValueError("No assets executed")

        # Return the last executed asset's artifact
        last_asset = self._execution_order[-1]
        if last_asset in self.asset_artifacts:
            return self.asset_artifacts[last_asset]

        # Find the last available artifact
        for asset_name in reversed(self._execution_order):
            if asset_name in self.asset_artifacts:
                return self.asset_artifacts[asset_name]

        raise ValueError("No artifacts produced")

    def get_completed_assets(self) -> Dict[str, Artefact]:
        """Get all completed asset artifacts."""
        return self.asset_artifacts.copy()
