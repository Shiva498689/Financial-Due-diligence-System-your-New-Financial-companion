from __future__ import annotations
import os
import math
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, Any
from fredapi import Fred
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
if FRED_API_KEY is None:
    raise RuntimeError(
        "Please set the environment variable FRED_API_KEY"
    )
fred = Fred(api_key=FRED_API_KEY)
mcp = FastMCP("Market Intelligence MCP")
def _ticker(ticker: str):
    return yf.Ticker(ticker)
def _history(ticker: str, period="2y"):
    return _ticker(ticker).history(period=period)
def _info(ticker: str):
    return _ticker(ticker).info
@mcp.tool()
def get_current_equity_price(
    ticker: str,
) -> Dict[str, Any]:
    info = _info(ticker)
    price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    return {
        "ticker": ticker,
        "current_equity_price": float(price)
    }
@mcp.tool()
def get_market_capitalization(
    ticker: str,
) -> Dict[str, Any]:
    """Fetches market capitalization."""
    info = _info(ticker)
    cap = info.get("marketCap")
    return {
        "ticker": ticker,
        "market_capitalization": float(cap)
    }
@mcp.tool()
def get_historical_equity_volatility_252d(
    ticker: str,
) -> Dict[str, Any]:
    hist = _history(ticker)
    close = hist["Close"]
    returns = np.log(close / close.shift(1))
    volatility = returns.std() * math.sqrt(252)
    return {
        "ticker": ticker,
        "historical_equity_volatility_252d": float(volatility)
    }
@mcp.tool()
def get_risk_free_rate() -> Dict[str, Any]:
   
    series = fred.get_series("DGS10")
    value = float(series.dropna().iloc[-1])
    return {
        "risk_free_rate": value / 100.0
    }
@mcp.tool()
def get_gnp_deflator() -> Dict[str, Any]:
    """Latest US GNP Deflator."""
    series = fred.get_series("A191RD3A086NBEA")
    value = float(series.dropna().iloc[-1])
    return {
        "gnp_deflator": value
    }
@mcp.tool()
def get_market_metrics(
    ticker: str,
) -> Dict[str, Any]:
    """Fetch all market metrics required by the
    Merton Distance-to-Default model.
    Returns:
    {
        "current_equity_price": float,
        "market_capitalization": float,
        "historical_equity_volatility_252d": float,
        "risk_free_rate": float,
        "gnp_deflator": float,
    }
    """

    try:
        info = _info(ticker)
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if price is None:
            raise ValueError("Unable to fetch current equity price.")
        market_cap = info.get("marketCap")

        if market_cap is None:
            raise ValueError("Unable to fetch market capitalization.")
        hist = _history(ticker)
        close = hist["Close"]
        returns = np.log(close / close.shift(1)).dropna()
        volatility = returns.std() * math.sqrt(252)
        risk_free_rate = float(
            fred.get_series("DGS10").dropna().iloc[-1]
        ) / 100.0
        gnp_deflator = float(
            fred.get_series("A191RD3A086NBEA").dropna().iloc[-1]
        )
        return {
            "current_equity_price": float(price),
            "market_capitalization": float(market_cap),
            "historical_equity_volatility_252d": float(volatility),
            "risk_free_rate": float(risk_free_rate),
            "gnp_deflator": float(gnp_deflator),
            "company_description": info.get("longBusinessSummary"),
        }
    except Exception as e:
        return {
            "error": str(e)
        }
@mcp.tool()
def ping() -> str:
    """
    Check whether the MCP server is alive.
    """
    return "Market Intelligence MCP Server Running."
if __name__ == "__main__":
    print("=" * 70)
    print("Starting Market Intelligence MCP Server...")
    print("=" * 70)
    mcp.run()