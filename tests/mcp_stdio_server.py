import asyncio
import argparse

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import StdioServerTransport

mcp = FastMCP("tools")


@mcp.tool()
def add_two_numbers(lhs: int, rhs: int) -> int:
    """
    Calculate the sum of two integers
    """
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
