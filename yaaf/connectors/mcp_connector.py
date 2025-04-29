from pydantic_ai.mcp import MCPServerHTTP


class MCPConnector:
    def __init__(self, url: str):
        self._url = url


async def run():
    async with MCPServerHTTP(url="http://localhost:8080/sse") as server:
        tools = await server.list_tools()
        print(tools)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
