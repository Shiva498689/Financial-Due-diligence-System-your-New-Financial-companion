from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
import asyncio
import pandas as pd
from typing import Any
import json
import yfinance as yf
import numpy as np
import requests
from scipy.optimize import fsolve
from scipy.stats import norm
from fredapi import Fred
from dotenv import load_dotenv
import os

ticker = "AAPL"
load_dotenv()
FRED_API_KEY = os.environ.get("FRED_API_KEY")

def _strip_financial_statements(data):
    """Recursively remove income statement and balance sheet keys from tool output."""
    DROP_KEYS = {
        "income_statement", "incomeStatement", "income_statements",
        "balance_sheet", "balanceSheet", "balance_sheets",
    }

    if isinstance(data, dict):
        return {
            k: _strip_financial_statements(v)
            for k, v in data.items()
            if k not in DROP_KEYS
        }
    if isinstance(data, list):
        return [_strip_financial_statements(item) for item in data]
    return data


async def get_tools(ticker: str , peers : list[str]) -> dict:
    all_tickers = [ticker] + peers
    async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "edgar_compare",
                arguments={
                    "identifiers": all_tickers,
                    "metrics": ["revenue", "net_income", "operating_income", "margins", "growth" , "assets" , "liabilities" , "equity" , "net_income"],
                },
            )

            # MCP tool results return content blocks; pull out the text payload
            raw = result.content[0].text
            data = json.loads(raw)

            cleaned = _strip_financial_statements(data)
            out = json.dumps(cleaned, indent=2)
            data1 = json.loads(out)
            return data1['data']['companies']
        
result =  asyncio.run(get_tools(ticker , ['MSFT']))

def get_risk_free_rate() -> float:
    """10Y Treasury yield via yfinance (^TNX)."""
    try:
        tnx = yf.download("^TNX", period="5d", progress=False, multi_level_index=False)["Close"].dropna()
        return float(tnx.iloc[-1]) / 100
    except Exception:
        return 0.0425  # fallback
    
def compute_hist_vol_252d(ticker: str, window: int = 252) -> float:
    """Annualized historical equity volatility over `window` trading days."""
    try:
        df = yf.download(ticker, period="1y",auto_adjust = False , progress=False)
        if ("Adj Close", ticker.upper()) in df.columns:
            prices = df[("Adj Close", ticker.upper())].dropna()
        else:
            # Agar purana yfinance version ho toh safely fallback
            prices = df["Adj Close"].dropna()
        log_ret = np.log(prices / prices.shift(1)).dropna()
        return float(log_ret.std() * np.sqrt(window))
    except Exception:
        return None

def compute_beta(ticker: str) -> float:
    """Beta vs S&P 500 — computed, with yfinance as fallback."""
    try:
        stock  = yf.download(ticker, period="1y", progress=False)["Close"].pct_change().dropna()
        market = yf.download("^GSPC", period="1y", progress=False)["Close"].pct_change().dropna()
        aligned = stock.align(market, join="inner")
        cov = np.cov(aligned[0], aligned[1])[0][1]
        var = np.var(aligned[1])
        return round(float(cov / var), 4)
    except Exception:
        # fallback to yfinance stored beta
        return yf.Ticker(ticker).info.get("beta")
    
def get_gnp_deflator() -> float:
    """GNP deflator (GNPDEF) from FRED."""
    try:
        fred = Fred(api_key=FRED_API_KEY)
        return float(fred.get_series("GNPDEF").iloc[-1])
    except Exception:
        return None
    
def calculate_live_mrp():
    # 1. Live Risk-Free Rate (^TNX - 10Y Treasury)
    rf = get_risk_free_rate()

    # 2. Market Return (^GSPC - S&P 500 5-Year CAGR)
    market_df = yf.download(
        "^GSPC", period="10y", progress=False, multi_level_index=False
    )
    prices = market_df["Close"].dropna()

    # CAGR Formula: (End / Start) ** (1 / Years) - 1
    total_years = 10
    rm = (prices.iloc[-1] / prices.iloc[0]) ** (1 / total_years) - 1

    # 3. MRP
    mrp = rm - rf
    
    return mrp

def get_market_cap(ticker: str) -> float:
    try:
        info = yf.Ticker(ticker).info
        mkt_cap = info.get("marketCap")
        if mkt_cap:
            mkt_cap = float(mkt_cap)
            return mkt_cap
    except Exception as e:
        print(f"[{ticker}] yfinance info failed: {e}")

    # ── Compute: price × shares outstanding ────────────────────────────────
    try:
        info   = yf.Ticker(ticker).info
        price  = (info.get("regularMarketPrice") 
                  or info.get("currentPrice") 
                  or info.get("previousClose"))
        shares = info.get("sharesOutstanding")

        if price and shares:
            mkt_cap = float(price) * float(shares)
            return mkt_cap
    except Exception as e:
        print(f"[{ticker}] Computed market cap failed: {e}")

    return None

def get_current_equity_price(ticker: str) -> float:

    try:
        fast = yf.Ticker(ticker).fast_info
        price = fast.get("last_price") or fast.get("regularMarketPrice")
        if price:
            price = float(price)
            return price
    except Exception as e:
        print(f"[{ticker}] yfinance fast_info failed: {e}")

    # ──  yfinance info (full fallback) ──────────────────────────────────────
    try:
        info = yf.Ticker(ticker).info
        price = (info.get("regularMarketPrice"))
        if price:
            price = float(price)
            return price
    except Exception as e:
        print(f"[{ticker}] yfinance info failed: {e}")

    print(f"[{ticker}] Price: unavailable")
    return None

async def enrich_peers_with_metrics(ticker : str , peers_list : list[str]) -> list:
    peers = await get_tools(ticker , peers_list)
    """
    Enriches an existing peer list with 5 additional metrics.
    
    Globals (fetched once):
      - risk_free_rate
      - gnp_deflator
    
    Per-ticker (fetched per peer):
      - historical_equity_volatility_252d
      - market_cap
      - current_equity_price
    """

    risk_free_rate = get_risk_free_rate()
    gnp_deflator   = get_gnp_deflator()

    enriched_peers = []

    for peer in peers:
        ticker = peer["identifier"]

        enriched = {
            "identifier" : peer["identifier"],
            "name"       : peer["name"],
            "cik"        : peer["cik"],
            "metrics"    : dict(peer["metrics"])  
        }

        hist_vol    = compute_hist_vol_252d(ticker)
        market_cap  = get_market_cap(ticker)
        equity_price = get_current_equity_price(ticker)

        enriched["metrics"].update({
            "risk_free_rate"                    : risk_free_rate,
            "gnp_deflator"                      : gnp_deflator,
            "historical_equity_volatility_252d" : hist_vol,
            "market_cap"                        : market_cap,
            "current_equity_price"              : equity_price,
        })

        enriched_peers.append(enriched)

    return json.dumps(enriched_peers , indent = 2)

print (asyncio.run(enrich_peers_with_metrics('AAPL' , ['MSFT'])))








