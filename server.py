from fastmcp import FastMCP
from get_best_peer import get_best_peers
from get_ratios import get_market_intel_ratios
import asyncio
import os
 
mcp = FastMCP("market_intelligence")

@mcp.tool()
async def get_best_competitor(ticker : str)-> str:
    return await get_best_peers(ticker)

@mcp.tool()
async def market_intel_ratios(ticker : str) -> list:
    return await get_market_intel_ratios(ticker)

if __name__ == "__main__":
    port = int(os.environ.get('PORT' , 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
