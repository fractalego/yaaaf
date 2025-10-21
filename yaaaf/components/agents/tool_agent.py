import logging
from typing import List

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import MCPToolExecutor
from yaaaf.components.agents.prompts import tool_agent_prompt_template
from yaaaf.components.client import BaseClient
from yaaaf.connectors.mcp_connector import MCPTools

_logger = logging.getLogger(__name__)


class ToolAgent(ToolBasedAgent):
    """Agent that executes MCP tools."""

    def __init__(self, client: BaseClient, tools: List[MCPTools]):
        """Initialize tool agent."""
        super().__init__(client, MCPToolExecutor(tools))
        self._system_prompt = tool_agent_prompt_template
        self._output_tag = "```tools"
        self._tools = tools

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Executes external tools via MCP (Model Context Protocol)"

    def get_description(self) -> str:
        return f"""
Tool agent: {self.get_info()}.
This agent can:
- Execute external tools and services
- Call APIs through MCP connectors
- Access system utilities
- Integrate with external applications

To call this agent write {self.get_opening_tag()} TOOL_REQUEST {self.get_closing_tag()}
Specify which tool you want to use and provide necessary parameters.
        """