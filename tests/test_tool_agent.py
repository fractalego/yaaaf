import unittest

from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.agents.tool_agent import ToolAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages
from yaaaf.connectors.mcp_connector import MCPConnector


class TestToolAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connector = MCPConnector(
            "http://localhost:8080/sse", "MCP server for number crunching"
        )

    async def test_single_tool(self):
        client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.4,
            max_tokens=1000,
        )
        messages = Messages().add_user_utterance("What is the sum of 5 and 10?")

        """Test that a single tool can be retrieved and called"""
        mcp_tools = await self.connector.get_tools()
        self.assertIsNotNone(mcp_tools)

        tool_agent = ToolAgent(client=client, tools=[mcp_tools])
        response = await tool_agent.query(messages)
        print(response)
        # retrieve artefacts from response
        artefacts = get_artefacts_from_utterance_content(response)
        self.assertGreater(len(artefacts), 0)
        expected = "15"
        self.assertIn(expected, artefacts[0].data.to_markdown())
