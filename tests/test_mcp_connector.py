import unittest

from yaaaf.connectors.mcp_connector import MCPSseConnector, MCPStdioConnector


class TestMCPSseConnector(unittest.TestCase):
    def setUp(self):
        self.connector = MCPSseConnector("http://localhost:8080/sse", "Test MCP Server")

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


class TestMCPStdioConnector(unittest.TestCase):
    def setUp(self):
        self.connector = MCPStdioConnector(
            "python", "Test MCP Stdio Server", ["-m", "tests.mcp_stdio_server"]
        )

    def test_connector_initialization(self):
        """Test that the stdio connector initializes correctly"""
        self.assertEqual(self.connector._command, "python")
        self.assertEqual(self.connector._args, ["-m", "tests.mcp_stdio_server"])
        self.assertEqual(self.connector._connector_description, "Test MCP Stdio Server")
        self.assertIsNone(self.connector._server)

    async def test_stdio_tools_can_be_retrieved(self):
        mcp_tools = await self.connector.get_tools()
        print(f"Connected to: {mcp_tools.server_description}")
        print(f"Available tools: {len(mcp_tools.tools)}")
        print(mcp_tools.get_tools_descriptions())

    async def test_stdio_tools_can_called(self):
        mcp_tools = await self.connector.get_tools()
        print(f"\nExample - calling tool by index 0: {mcp_tools[0].name.strip()}")
        print(f"which has schema: {mcp_tools[0].inputSchema}")
        result = await mcp_tools.call_tool_by_index(0, arguments={"lhs": 5, "rhs": 10})
        print("Result from tool call:", result)


if __name__ == "__main__":
    unittest.main()
