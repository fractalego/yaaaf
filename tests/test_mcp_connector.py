import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from yaaaf.connectors.mcp_connector import MCPConnector, MCPTools, ToolDescription


class TestMCPConnector(unittest.TestCase):
    def setUp(self):
        self.connector = MCPConnector("http://localhost:8080/sse", "Test MCP Server")

    def test_connector_initialization(self):
        """Test that the connector initializes correctly"""
        self.assertEqual(self.connector._url, "http://localhost:8080/sse")
        self.assertEqual(self.connector._connector_description, "Test MCP Server")
        self.assertIsNone(self.connector._server)

    async def test_tools_can_be_retrieved(self):
        mcp_tools = await self.connector.get_tools()
        print(f"Connected to: {mcp_tools.server_description}")
        print(f"Available tools: {len(mcp_tools.tools)}")
        print(mcp_tools.get_tools_descriptions())

    async def test_tools_can_called(self):
        mcp_tools = await self.connector.get_tools()
        print(f"\nExample - calling tool by index 0: {mcp_tools[0].name.strip()}")
        print(f"which has schema: {mcp_tools[0].inputSchema}")
        result = await mcp_tools.call_tool_by_index(0, arguments={"lhs": 5, "rhs": 10})
        print("Result from tool call:", result)



if __name__ == "__main__":
    unittest.main()