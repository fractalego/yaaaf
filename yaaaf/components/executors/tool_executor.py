import logging
import json
from typing import Dict, Any, Optional, Tuple, List

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note
from yaaaf.connectors.mcp_connector import MCPTools

_logger = logging.getLogger(__name__)


class MCPToolExecutor(ToolExecutor):
    """Executor for MCP tools execution."""

    def __init__(self, tools: List[MCPTools]):
        """Initialize MCP tool executor."""
        self._storage = ArtefactStorage()
        self._tools = tools
        self._tools_description = "\n".join(
            [
                f"Tool group index {group_index}:\n{tool_group.get_tools_descriptions()}\n\n"
                for group_index, tool_group in enumerate(tools)
            ]
        )
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for tool execution."""
        return {
            "messages": messages,
            "notes": notes or [],
            "tools": self._tools,
            "tools_description": self._tools_description
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract tool call from response."""
        return get_first_text_between_tags(response, "```tools", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Execute MCP tool call."""
        try:
            tools = context["tools"]
            tool_call = instruction.strip()
            
            # Parse the tool call (expect JSON format)
            try:
                call_data = json.loads(tool_call)
                tool_group_index = call_data.get("group_index", 0)
                tool_name = call_data.get("tool_name")
                arguments = call_data.get("arguments", {})
            except json.JSONDecodeError:
                # Fallback: treat as simple tool name
                tool_name = tool_call
                tool_group_index = 0
                arguments = {}
            
            if tool_group_index >= len(tools):
                return None, f"Invalid tool group index: {tool_group_index}"
            
            tool_group = tools[tool_group_index]
            
            # Execute the tool
            result = await tool_group.call_tool(tool_name, arguments)
            
            tool_result = {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "group_index": tool_group_index
            }
            
            return tool_result, None
            
        except Exception as e:
            error_msg = f"Error executing tool '{instruction}': {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def validate_result(self, result: Any) -> bool:
        """Validate tool execution result."""
        return (result is not None and 
                isinstance(result, dict) and 
                "tool_name" in result and 
                "result" in result)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform tool result to artifact."""
        content = json.dumps(result, indent=2)
        
        return Artefact(
            id=artifact_id,
            type="text",
            code=content,  # Use 'code' field for text content
            description=f"Result from tool: {result['tool_name']}"
        )