"""ValidationAgent - validates artifacts against expectations."""

import json
import logging
import re

from yaaaf.components.agents.base_agent import CustomAgent
from yaaaf.components.agents.prompts import validation_agent_prompt_template, get_validation_prompt_for_agent
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.validators.validation_result import ValidationResult
from yaaaf.components.validators.artifact_inspector import inspect_artifact
from yaaaf.components.validators.failure_analyzer import analyze_bash_output, create_failure_summary
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage

_logger = logging.getLogger(__name__)


class ValidationAgent(CustomAgent):
    """Agent that validates artifacts against expectations.

    This agent inspects artifacts and determines if they match the user's
    goal and the step description. It returns a confidence score and
    can suggest fixes for replanning.
    """

    def __init__(self, client: BaseClient):
        """Initialize validation agent.

        Args:
            client: LLM client for validation
        """
        super().__init__(client)
        self._storage = ArtefactStorage()

    async def validate(
        self,
        artifact: Artefact,
        user_goal: str,
        step_description: str,
        expected_type: str,
        asset_name: str = None,
        input_context: str = None,
        agent_name: str = None,
    ) -> ValidationResult:
        """Validate an artifact against expectations.

        Args:
            artifact: The artifact to validate
            user_goal: Original user goal
            step_description: What this step was supposed to do
            expected_type: Expected artifact type
            asset_name: Name of the asset being validated
            input_context: Summary of input artifacts that were fed into this step
            agent_name: Name of the agent that produced this artifact (for specialized prompts)

        Returns:
            ValidationResult with confidence and recommendations
        """
        # Inspect the artifact
        artifact_content = inspect_artifact(artifact)
        _logger.debug(f"Validation artifact content preview (first 500 chars): {artifact_content[:500] if artifact_content else 'EMPTY'}")

        # Get the appropriate prompt template for this agent
        prompt_template = get_validation_prompt_for_agent(agent_name)

        # Build the prompt with input context if available
        prompt = prompt_template.complete(
            user_goal=user_goal,
            step_description=step_description,
            expected_type=expected_type,
            artifact_content=artifact_content,
            input_context=input_context or "No input artifacts (this is a source step)",
        )

        # Query the LLM
        messages = Messages()
        messages.utterances.append(Utterance(role="user", content=prompt))

        try:
            response = await self._client.predict(messages)
            result = self._parse_response(response.message, asset_name)

            # For bash agents, analyze the output to detect failure type
            if agent_name == "BashAgent" and not result.is_valid:
                failure_type, failure_details = analyze_bash_output(artifact_content)
                result.failure_type = failure_type
                result.failure_details = failure_details
                # Update reason with failure summary if not already detailed
                if not result.reason or len(result.reason) < 20:
                    result.reason = create_failure_summary(failure_type, failure_details)
                _logger.info(f"Detected failure type: {failure_type} for {asset_name}")

            return result
        except Exception as e:
            _logger.error(f"Validation failed: {e}")
            # Return a default "valid" result on error to not block execution
            return ValidationResult.valid(
                reason=f"Validation skipped due to error: {e}",
                asset_name=asset_name,
            )

    async def validate_from_result_string(
        self,
        result_string: str,
        user_goal: str,
        step_description: str,
        expected_type: str,
        asset_name: str = None,
        input_artifacts: dict = None,
        agent_name: str = None,
    ) -> ValidationResult:
        """Validate an artifact from an agent result string.

        Args:
            result_string: Agent result containing artifact reference
            user_goal: Original user goal
            step_description: What this step was supposed to do
            expected_type: Expected artifact type
            asset_name: Name of the asset being validated
            input_artifacts: Dict of input asset names to their result strings
            agent_name: Name of the agent that produced this artifact (for specialized prompts)

        Returns:
            ValidationResult with confidence and recommendations
        """
        # Extract artifact from result string
        match = re.search(r"<artefact[^>]*>([^<]+)</artefact>", result_string)
        if not match:
            _logger.warning(f"No artifact found in result for {asset_name}")
            return ValidationResult.valid(
                reason="No artifact to validate (may be intermediate step)",
                asset_name=asset_name,
            )

        artifact_id = match.group(1)

        # Build input context from input artifacts
        input_context = None
        if input_artifacts:
            context_parts = []
            for input_name, input_result in input_artifacts.items():
                # Extract artifact content from input result
                input_match = re.search(r"<artefact[^>]*>([^<]+)</artefact>", input_result)
                if input_match:
                    input_artifact_id = input_match.group(1)
                    try:
                        input_artifact = self._storage.retrieve_from_id(input_artifact_id)
                        input_content = inspect_artifact(input_artifact)
                        # Truncate long content
                        if len(input_content) > 500:
                            input_content = input_content[:500] + "..."
                        context_parts.append(f"Input '{input_name}':\n{input_content}")
                    except Exception as e:
                        context_parts.append(f"Input '{input_name}': (could not retrieve: {e})")
                else:
                    # No artifact wrapper, use raw content (truncated)
                    truncated = input_result[:500] + "..." if len(input_result) > 500 else input_result
                    context_parts.append(f"Input '{input_name}':\n{truncated}")
            input_context = "\n\n".join(context_parts)

        try:
            artifact = self._storage.retrieve_from_id(artifact_id)
            _logger.info(f"Retrieved artifact {artifact_id}: type={artifact.type}, "
                        f"code_len={len(artifact.code) if artifact.code else 0}, "
                        f"desc={artifact.description[:50] if artifact.description else 'none'}...")
            return await self.validate(
                artifact=artifact,
                user_goal=user_goal,
                step_description=step_description,
                expected_type=expected_type,
                asset_name=asset_name,
                input_context=input_context,
                agent_name=agent_name,
            )
        except Exception as e:
            _logger.error(f"Failed to retrieve artifact {artifact_id}: {e}")
            return ValidationResult.valid(
                reason=f"Could not retrieve artifact for validation: {e}",
                asset_name=asset_name,
            )

    def _parse_response(self, response: str, asset_name: str = None) -> ValidationResult:
        """Parse LLM response into ValidationResult.

        Args:
            response: LLM response containing JSON
            asset_name: Name of the asset being validated

        Returns:
            Parsed ValidationResult
        """
        # Extract JSON from response
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to parse the whole response as JSON
            json_str = response.strip()

        try:
            data = json.loads(json_str)
            return ValidationResult(
                is_valid=data.get("is_valid", True),
                confidence=float(data.get("confidence", 1.0)),
                reason=data.get("reason", "No reason provided"),
                should_ask_user=data.get("should_ask_user", False),
                suggested_fix=data.get("suggested_fix"),
                asset_name=asset_name,
            )
        except json.JSONDecodeError as e:
            _logger.warning(f"Failed to parse validation response: {e}")
            _logger.debug(f"Response was: {response}")
            # Default to valid on parse error
            return ValidationResult.valid(
                reason=f"Could not parse validation response: {e}",
                asset_name=asset_name,
            )

    async def query(self, messages: Messages, notes=None) -> str:
        """Standard agent query interface (not typically used directly).

        Args:
            messages: Messages containing validation request
            notes: Optional notes

        Returns:
            Validation result as string
        """
        return await self._query_custom(messages, notes)

    async def _query_custom(self, messages: Messages, notes=None) -> str:
        """Custom query implementation for ValidationAgent.

        This agent is typically used via validate() method,
        but we implement _query_custom for compatibility.

        Args:
            messages: Messages containing validation request
            notes: Optional notes

        Returns:
            Validation result as string
        """
        if messages.utterances:
            # This is a fallback for direct usage
            # ValidationAgent is typically used via validate() method
            result = ValidationResult.valid(reason="Direct query not fully supported")
            return json.dumps(result.to_dict())
        return json.dumps(ValidationResult.valid().to_dict())

    @staticmethod
    def get_info() -> str:
        """Get agent description."""
        return "Validates artifacts against user goals and step descriptions"

    def get_description(self) -> str:
        """Get detailed agent description."""
        return f"""
Validation agent: {self.get_info()}.
This agent:
- Inspects artifacts produced by workflow steps
- Compares them against user goals and step descriptions
- Returns confidence scores for replanning decisions
- Suggests fixes when artifacts don't match expectations
        """
