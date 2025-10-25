import logging
from typing import Dict, Any, Optional, Tuple, List

from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.agents.artefacts import Artefact
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags

_logger = logging.getLogger(__name__)


class PlannerExecutor(ToolExecutor):
    """Executor for creating asset-based workflow execution plans."""

    def __init__(self, available_agents: List[Dict[str, Any]], output_tag: str = "```yaml"):
        """Initialize planner executor.
        
        Args:
            available_agents: List of available agents with their taxonomies
            output_tag: Tag used to extract the workflow output
        """
        self._available_agents = available_agents
        self._output_tag = output_tag

    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for planning."""
        return {
            "messages": messages,
            "notes": notes or [],
            "available_agents": self._available_agents
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract workflow specification from response."""
        tag = self._output_tag.replace('```', '').replace('`', '')
        return get_first_text_between_tags(response, f"```{tag}", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Process the generated workflow."""
        try:
            import yaml
            
            # The instruction should be a valid YAML workflow
            # Basic validation
            if not instruction:
                return None, "No workflow specification found"
            
            # Check for basic YAML structure and parse
            try:
                workflow_data = yaml.safe_load(instruction)
                if not isinstance(workflow_data, dict):
                    return None, "Invalid workflow format: root must be a dictionary"
                
                if "assets" not in workflow_data:
                    return None, "Invalid workflow format: missing 'assets' section"
                
                # Basic asset validation
                assets = workflow_data["assets"]
                if not isinstance(assets, dict):
                    return None, "Invalid workflow format: 'assets' must be a dictionary"
                
                # Validate each asset has required fields
                for asset_name, asset_config in assets.items():
                    if not isinstance(asset_config, dict):
                        return None, f"Invalid asset '{asset_name}': must be a dictionary"
                    
                    required_fields = ["agent", "description", "type"]
                    for field in required_fields:
                        if field not in asset_config:
                            return None, f"Invalid asset '{asset_name}': missing required field '{field}'"
                
            except yaml.YAMLError as e:
                return None, f"Invalid YAML format: {str(e)}"
            
            # The workflow is valid - return it
            return instruction, None
            
        except Exception as e:
            error_msg = f"Error processing workflow: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def validate_result(self, result: Any) -> bool:
        """Validate workflow result."""
        return result is not None and isinstance(result, str) and "assets:" in result

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform workflow to artifact."""
        return Artefact(
            id=artifact_id,
            type="text",
            code=result,  # The YAML workflow
            description="Execution plan workflow in YAML format"
        )