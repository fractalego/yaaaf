"""ValidationAgent - validates artifacts against expectations."""

import json
import logging
import re

from yaaaf.components.agents.base_agent import CustomAgent
from yaaaf.components.agents.prompts import validation_agent_prompt_template
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.validators.validation_result import ValidationResult
from yaaaf.components.validators.artifact_inspector import inspect_artifact
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
    ) -> ValidationResult:
        """Validate an artifact against expectations.

        Args:
            artifact: The artifact to validate
            user_goal: Original user goal
            step_description: What this step was supposed to do
            expected_type: Expected artifact type
            asset_name: Name of the asset being validated

        Returns:
            ValidationResult with confidence and recommendations
        """
        # Inspect the artifact
        artifact_content = inspect_artifact(artifact)

        # Build the prompt
        prompt = validation_agent_prompt_template.complete(
            user_goal=user_goal,
            step_description=step_description,
            expected_type=expected_type,
            artifact_content=artifact_content,
        )

        # Query the LLM
        messages = Messages()
        messages.utterances.append(Utterance(role="user", content=prompt))

        try:
            response = await self._client.predict(messages)
            result = self._parse_response(response.message, asset_name)
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
    ) -> ValidationResult:
        """Validate an artifact from an agent result string.

        Args:
            result_string: Agent result containing artifact reference
            user_goal: Original user goal
            step_description: What this step was supposed to do
            expected_type: Expected artifact type
            asset_name: Name of the asset being validated

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

        try:
            artifact = self._storage.retrieve_from_id(artifact_id)
            return await self.validate(
                artifact=artifact,
                user_goal=user_goal,
                step_description=step_description,
                expected_type=expected_type,
                asset_name=asset_name,
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
