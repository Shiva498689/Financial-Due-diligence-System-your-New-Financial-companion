from fastmcp import FastMCP
from get_peers import build_top_peers
from sec_tool import condense_all
from news_tool import main

mcp = FastMCP("market_intelligence")

# COMMON PEERS FUNCTION 
async def get_peers_tool(ticker : str) :
    return await build_top_peers(ticker)

@mcp.tool()
async def sec_data(ticker : str) -> dict:
    """Fetches the data from 4 sections of the 10K sec filings"""
    peers_list = await get_peers_tool(ticker)
    return await condense_all(ticker , peers_list=peers_list)

@mcp.tool()
async def get_recent_news(ticker : str) -> str:
    """Fetches the recent news of the company"""
    peers_list = await get_peers_tool(ticker)

    return await main(ticker , peers_list)

if __name__ == "__main__":
    mcp.run(transport = "sse")