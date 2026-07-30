import aiohttp
import os
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Placeholders for the API Key. The user will replace these.
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "PKIVCVQ4HS47YSEPCVM7X5KYLO")
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "9eCZkHXWcPoov3h7e7gm9BDveJx4fNi1WUtgtTzFeUwo")

# Alpaca News API Endpoint
ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"

async def fetch_alpaca_news(symbol: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """
    Fetches news from the Alpaca API asynchronously.
    Optionally filters by symbol.
    """
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json"
    }

    params = {
        "limit": str(limit),
        "include_content": "true",
        "exclude_contentless": "true"
    }

    if symbol:
        params["symbols"] = symbol.upper()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ALPACA_NEWS_URL, headers=headers, params=params) as response:
                if response.status == 401 or response.status == 403:
                    logger.error(f"Alpaca API Authentication Failed. Please check your API keys.")
                    return {"news": [], "error": "Authentication failed. Check API keys."}
                
                response.raise_for_status()
                data = await response.json()
                
                return {"news": data.get("news", []), "error": None}
    except Exception as e:
        logger.error(f"Error fetching news from Alpaca: {e}")
        return {"news": [], "error": str(e)}
