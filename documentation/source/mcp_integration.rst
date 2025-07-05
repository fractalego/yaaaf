MCP Integration
===============

YAAAF includes comprehensive support for **MCP (Model Context Protocol)** integration, enabling seamless connection to external tools and services. MCP is a standardized protocol for connecting AI models to external data sources and tools.

.. contents::
   :local:
   :depth: 2

Overview
--------

The MCP integration in YAAAF provides:

* **Multiple Transport Methods**: Support for both SSE (Server-Sent Events) and stdio communication protocols
* **Unified Interface**: Common API for all MCP server types
* **Tool Agent Integration**: Seamless integration with YAAAF's ToolAgent for AI-powered tool usage
* **Flexible Configuration**: Easy setup for different MCP server configurations
* **Type Safety**: Full typing support for tool schemas and responses

Architecture
------------

The MCP integration consists of several key components:

.. code-block:: text

   MCPConnector (Base Class)
   ├── MCPSseConnector (HTTP/SSE-based servers)
   └── MCPStdioConnector (Command-line/stdio-based servers)
   
   MCPTools (Tool container)
   ├── Tool descriptions and schemas
   ├── Server reference
   └── Tool execution methods

Base Classes
~~~~~~~~~~~~

**MCPConnector** (Abstract Base Class)
   Common functionality for all MCP connector types:
   
   * Connection management
   * Tool discovery and listing
   * Tool execution interface
   * Error handling and cleanup

**MCPTools**
   Container for MCP tools and server reference:
   
   * Tool metadata and schemas
   * Server connection reference
   * Tool execution methods
   * Unified tool access interface

Transport Types
---------------

SSE (Server-Sent Events) Transport
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``MCPSseConnector`` connects to MCP servers over HTTP using Server-Sent Events.

**Use Cases:**
- Remote MCP servers
- Web-based tools and services
- Cloud-hosted MCP servers
- Third-party MCP services

**Configuration:**

.. code-block:: python

   from yaaaf.connectors.mcp_connector import MCPSseConnector
   
   # Create SSE connector
   connector = MCPSseConnector(
       url="http://localhost:8080/sse",
       description="Remote MCP Server"
   )
   
   # Get available tools
   tools = await connector.get_tools()
   
   # Use tools
   result = await tools.call_tool("tool_name", {"arg": "value"})

**Server Requirements:**
- HTTP server with SSE endpoint
- MCP protocol compliance
- CORS support (if needed)

Stdio Transport
~~~~~~~~~~~~~~~

The ``MCPStdioConnector`` connects to MCP servers via command-line stdio communication.

**Use Cases:**
- Local MCP servers
- Command-line tools
- Custom MCP implementations
- Development and testing

**Configuration:**

.. code-block:: python

   from yaaaf.connectors.mcp_connector import MCPStdioConnector
   
   # Create stdio connector
   connector = MCPStdioConnector(
       command="python",
       description="Local MCP Server",
       args=["-m", "my_mcp_server"]
   )
   
   # Get available tools
   tools = await connector.get_tools()
   
   # Use tools
   result = await tools.call_tool("tool_name", {"arg": "value"})

**Server Requirements:**
- Executable command
- Stdio-based MCP protocol
- Proper argument handling

MCP Server Examples
-------------------

SSE Server Example
~~~~~~~~~~~~~~~~~~

Here's a complete example of an SSE-based MCP server:

.. code-block:: python

   # tests/mcp_sse_server.py
   import argparse
   import uvicorn
   
   from mcp.server import Server
   from mcp.server.fastmcp import FastMCP
   from mcp.server.sse import SseServerTransport
   from starlette.applications import Starlette
   from starlette.requests import Request
   from starlette.routing import Route, Mount
   
   mcp = FastMCP("tools")
   
   @mcp.tool()
   def add_two_numbers(lhs: int, rhs: int) -> int:
       """Calculate the sum of two integers"""
       return lhs + rhs
   
   def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
       """Create a Starlette application for the MCP server with SSE."""
       sse = SseServerTransport("/messages/")
   
       async def handle_sse(request: Request) -> None:
           async with sse.connect_sse(
               request.scope,
               request.receive,
               request._send,
           ) as (read_stream, write_stream):
               await mcp_server.run(
                   read_stream,
                   write_stream,
                   mcp_server.create_initialization_options(),
               )
   
       return Starlette(
           debug=debug,
           routes=[
               Route("/sse", endpoint=handle_sse),
               Mount("/messages/", app=sse.handle_post_message),
           ],
       )
   
   if __name__ == "__main__":
       mcp_server = mcp._mcp_server
       parser = argparse.ArgumentParser(description="Run MCP SSE-based server")
       parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
       parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
       args = parser.parse_args()
   
       starlette_app = create_starlette_app(mcp_server, debug=True)
       uvicorn.run(starlette_app, host=args.host, port=args.port)

**Running the SSE Server:**

.. code-block:: bash

   python tests/mcp_sse_server.py --host localhost --port 8080

Stdio Server Example
~~~~~~~~~~~~~~~~~~~~

Here's a complete example of a stdio-based MCP server:

.. code-block:: python

   # tests/mcp_stdio_server.py
   import asyncio
   import argparse
   
   from mcp.server import Server
   from mcp.server.fastmcp import FastMCP
   from mcp.server.stdio import StdioServerTransport
   
   mcp = FastMCP("tools")
   
   @mcp.tool()
   def add_two_numbers(lhs: int, rhs: int) -> int:
       """Calculate the sum of two integers"""
       return lhs + rhs
   
   async def run_stdio_server(mcp_server: Server) -> None:
       """Run an MCP server with stdio transport."""
       stdio = StdioServerTransport()
       
       async with stdio.connect_stdio() as (read_stream, write_stream):
           await mcp_server.run(
               read_stream,
               write_stream,
               mcp_server.create_initialization_options(),
           )
   
   if __name__ == "__main__":
       mcp_server = mcp._mcp_server
       parser = argparse.ArgumentParser(description="Run MCP stdio-based server")
       args = parser.parse_args()
   
       asyncio.run(run_stdio_server(mcp_server))

**Running the Stdio Server:**

.. code-block:: bash

   python tests/mcp_stdio_server.py

Tool Agent Integration
----------------------

The ``ToolAgent`` in YAAAF provides AI-powered integration with MCP tools. It can:

* Automatically discover and understand available tools
* Plan tool usage based on user queries
* Execute complex workflows involving multiple tools
* Handle tool errors and retries
* Generate structured outputs and artifacts

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from yaaaf.components.agents.tool_agent import ToolAgent
   from yaaaf.components.client import OllamaClient
   from yaaaf.components.data_types import Messages
   from yaaaf.connectors.mcp_connector import MCPSseConnector
   
   # Setup client and connector
   client = OllamaClient(model="qwen2.5:32b", temperature=0.4)
   connector = MCPSseConnector(
       "http://localhost:8080/sse", 
       "Math Tools Server"
   )
   
   # Get tools from MCP server
   mcp_tools = await connector.get_tools()
   
   # Create tool agent
   tool_agent = ToolAgent(client=client, tools=[mcp_tools])
   
   # Query the agent
   messages = Messages().add_user_utterance("What is the sum of 15 and 27?")
   response = await tool_agent.query(messages)
   
   print(response)

Advanced Usage
~~~~~~~~~~~~~~

The ToolAgent supports multiple tool groups and complex workflows:

.. code-block:: python

   # Multiple MCP tool groups
   math_tools = await math_connector.get_tools()
   file_tools = await file_connector.get_tools()
   web_tools = await web_connector.get_tools()
   
   # Create agent with multiple tool groups
   tool_agent = ToolAgent(
       client=client, 
       tools=[math_tools, file_tools, web_tools]
   )
   
   # Complex multi-step query
   messages = Messages().add_user_utterance(
       "Read the numbers from data.csv, calculate their sum, "
       "and search for information about the result online"
   )
   
   response = await tool_agent.query(messages)

Tool Agent Features
~~~~~~~~~~~~~~~~~~~

**Automatic Tool Discovery:**
   The agent automatically understands available tools and their capabilities from tool descriptions and schemas.

**Intelligent Planning:**
   Uses the LLM to plan which tools to use and in what order based on the user's query.

**Error Handling:**
   Gracefully handles tool errors and can retry with different approaches.

**Artifact Generation:**
   Creates structured artifacts (tables, charts, etc.) from tool outputs.

**Multi-step Workflows:**
   Can execute complex workflows involving multiple tools and intermediate steps.

Configuration Examples
----------------------

Development Setup
~~~~~~~~~~~~~~~~~

For development and testing, you can use both SSE and stdio servers:

.. code-block:: python

   # config.json (example)
   {
       "mcp_servers": [
           {
               "type": "sse",
               "url": "http://localhost:8080/sse",
               "description": "Development SSE Server"
           },
           {
               "type": "stdio",
               "command": "python",
               "args": ["-m", "tests.mcp_stdio_server"],
               "description": "Development Stdio Server"
           }
       ]
   }

Production Setup
~~~~~~~~~~~~~~~~

For production, you might connect to remote MCP services:

.. code-block:: python

   # Production configuration
   {
       "mcp_servers": [
           {
               "type": "sse",
               "url": "https://api.example.com/mcp/sse",
               "description": "Production API Server"
           },
           {
               "type": "stdio",
               "command": "docker",
               "args": ["run", "--rm", "my-mcp-server:latest"],
               "description": "Containerized MCP Server"
           }
       ]
   }

Testing
-------

YAAAF includes comprehensive tests for MCP integration:

Running MCP Tests
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Run all MCP connector tests
   python -m unittest tests.test_mcp_connector
   
   # Run tool agent tests with MCP
   python -m unittest tests.test_tool_agent
   
   # Run specific test methods
   python -m unittest tests.test_mcp_connector.TestMCPSseConnector.test_tools_can_be_retrieved
   python -m unittest tests.test_mcp_connector.TestMCPStdioConnector.test_stdio_tools_can_be_retrieved

Test Structure
~~~~~~~~~~~~~~

.. code-block:: python

   # Test both SSE and stdio connectors
   class TestMCPSseConnector(unittest.TestCase):
       def setUp(self):
           self.connector = MCPSseConnector(
               "http://localhost:8080/sse", 
               "Test MCP Server"
           )
   
   class TestMCPStdioConnector(unittest.TestCase):
       def setUp(self):
           self.connector = MCPStdioConnector(
               "python", 
               "Test MCP Stdio Server", 
               ["-m", "tests.mcp_stdio_server"]
           )

Best Practices
--------------

Server Development
~~~~~~~~~~~~~~~~~~

1. **Use FastMCP**: Simplifies MCP server development with decorators
2. **Type Annotations**: Provide clear type hints for tool parameters
3. **Error Handling**: Implement proper error handling in tool functions
4. **Documentation**: Include clear docstrings for all tools
5. **Testing**: Test both SSE and stdio transports

Client Integration
~~~~~~~~~~~~~~~~~~

1. **Connection Management**: Always properly disconnect from servers
2. **Error Handling**: Handle connection failures gracefully
3. **Tool Discovery**: Cache tool schemas when possible
4. **Async/Await**: Use proper async patterns for tool calls
5. **Resource Cleanup**: Ensure proper cleanup of resources

Security Considerations
~~~~~~~~~~~~~~~~~~~~~~~

1. **Input Validation**: Validate all tool inputs
2. **Authentication**: Implement proper authentication for remote servers
3. **Rate Limiting**: Implement rate limiting for tool calls
4. **Sandboxing**: Consider sandboxing for untrusted MCP servers
5. **Logging**: Log all tool executions for audit trails

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**Connection Failures:**
   - Check server URL and port
   - Verify server is running
   - Check network connectivity
   - Validate MCP protocol compliance

**Tool Execution Errors:**
   - Validate tool parameters
   - Check tool schema compliance
   - Verify server implementation
   - Review error logs

**Performance Issues:**
   - Monitor connection pooling
   - Check server response times
   - Optimize tool parameter sizes
   - Consider caching strategies

Debug Mode
~~~~~~~~~~

Enable debug mode for detailed logging:

.. code-block:: python

   import logging
   logging.basicConfig(level=logging.DEBUG)
   
   # Your MCP connector code here
   connector = MCPSseConnector(url="...", description="...")
   tools = await connector.get_tools()

This will provide detailed information about MCP protocol communication and any issues that arise.

API Reference
-------------

MCPConnector (Base Class)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class MCPConnector(ABC):
       def __init__(self, description: str)
       async def get_tools(self) -> MCPTools
       async def disconnect(self) -> None
       async def _create_server(self) -> Union[MCPServerSSE, MCPServerStdio]  # Abstract

MCPSseConnector
~~~~~~~~~~~~~~~

.. code-block:: python

   class MCPSseConnector(MCPConnector):
       def __init__(self, url: str, description: str)
       async def _create_server(self) -> MCPServerSSE

MCPStdioConnector
~~~~~~~~~~~~~~~~~

.. code-block:: python

   class MCPStdioConnector(MCPConnector):
       def __init__(self, command: str, description: str, args: Optional[List[str]] = None)
       async def _create_server(self) -> MCPServerStdio

MCPTools
~~~~~~~~

.. code-block:: python

   class MCPTools(BaseModel):
       server_description: str
       tools: List[ToolDescription]
       server: Union[MCPServerSSE, MCPServerStdio]
       
       def __getitem__(self, index: int) -> ToolDescription
       def __len__(self) -> int
       def get_tools_descriptions(self) -> str
       async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any
       async def call_tool_by_index(self, index: int, arguments: Dict[str, Any]) -> Any