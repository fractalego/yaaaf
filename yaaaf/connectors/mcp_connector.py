from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from pydantic_ai.mcp import MCPServerSSE


class ToolDescription(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPTools(BaseModel):
    server_description: str
    tools: List[ToolDescription]
    server: MCPServerSSE

    class Config:
        arbitrary_types_allowed = True

    def __getitem__(self, index: int) -> ToolDescription:
        """Allow indexing to get tools by index"""
        return self.tools[index]

    def __len__(self) -> int:
        """Return number of tools"""
        return len(self.tools)

    def get_tools_descriptions(self) -> str:
        """Get a string representation of available tool descriptions"""
        return "\n".join(
            f"{i}) Name: {tool.name}, Description: {tool.description.strip()}, Input schema: {str(tool.inputSchema).strip()}"
            for i, tool in enumerate(self.tools)
        )

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool by name with given arguments"""
        if not self.server:
            raise RuntimeError("MCP server connection not available")

        return await self.server.call_tool(tool_name, arguments)

    async def call_tool_by_index(self, index: int, arguments: Dict[str, Any]) -> Any:
        """Call a tool by index with given arguments"""
        if index < 0 or index >= len(self.tools):
            raise IndexError(f"Tool index {index} out of range")

        tool_name = self.tools[index].name
        return await self.call_tool(tool_name, arguments)


class MCPConnector:
    def __init__(self, url: str, description: str):
        self._url = url
        self._server: Optional[MCPServerSSE] = None
        self._connector_description = description

    async def get_tools(self) -> MCPTools:
        """Connect to MCP server and return Tool object with server and tool descriptions"""
        try:
            self._server = MCPServerSSE(url=self._url)
            await self._server.__aenter__()

            # Get available tools
            tools_response = await self._server.list_tools()
            tool_descriptions = []

            for tool_info in tools_response:
                tool_desc = ToolDescription(
                    name=tool_info.name,
                    description=tool_info.description or "",
                    inputSchema=tool_info.parameters_json_schema or {},
                )
                tool_descriptions.append(tool_desc)

            # Create Tool object with server reference
            mcp_tools = MCPTools(
                server_description=self._connector_description,
                tools=tool_descriptions,
                server=self._server,
            )

            return mcp_tools

        except Exception as e:
            if self._server:
                await self._server.__aexit__(None, None, None)
            raise e

    async def disconnect(self):
        """Disconnect from MCP server"""
        if self._server:
            await self._server.__aexit__(None, None, None)
            self._server = None
