from fastmcp import FastMCP
from get_peers_ import main as fetch_peers
from sec_tool import condense_all
from news_tool import main_news
import asyncio

mcp = FastMCP("market_intelligence")

# COMMON PEERS FUNCTION 
@mcp.tool()
async def get_peers_tool(ticker : str) :
    return await asyncio.to_thread(fetch_peers, ticker)

@mcp.tool()
async def sec_data(ticker: str, peers_list: list[str] | None = None) -> dict:
    if peers_list is None:
        peers_list = await get_peers_tool(ticker)

    return await condense_all(ticker, peers_list=peers_list)


@mcp.tool()
async def get_recent_news(ticker: str, peers_list: list[str] | None = None) -> str:
    if peers_list is None:
        peers_list = await get_peers_tool(ticker)

    return await main_news(ticker, peers_list)

if __name__ == "__main__":
    mcp.run(transport = "sse")
