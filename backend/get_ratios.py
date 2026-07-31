import asyncio
import yfinance as yf
import numpy as np
from fredapi import Fred
from dotenv import load_dotenv
import os
 
load_dotenv()
FRED_API_KEY = os.environ.get("FRED_API_KEY")

async def get_risk_free_rate() -> float:
    try:
        tnx = (await asyncio.to_thread(lambda: yf.download("^TNX", period="5d", progress=False, multi_level_index=False)))["Close"].dropna()
        return float(tnx.iloc[-1]) / 100
    except Exception:
        return 0.0425  

async def compute_hist_vol_252d(ticker: str, window: int = 252) -> float:
    try:
        df = await asyncio.to_thread(lambda: yf.download(ticker, period="1y",auto_adjust = False , progress=False))
        if ("Adj Close", ticker.upper()) in df.columns:
            prices = df[("Adj Close", ticker.upper())].dropna()
        else:
            # Fallback for alternative yfinance dataframe structure
            prices = df["Adj Close"].dropna()
        log_ret = np.log(prices / prices.shift(1)).dropna()
        return float(log_ret.std() * np.sqrt(window))
    except Exception:
        return None

async def get_gnp_deflator() -> float:
    try:
        return float((await asyncio.to_thread(lambda: Fred(api_key=FRED_API_KEY).get_series("GNPDEF"))).iloc[-1])
    except Exception:
        return None

async def get_market_cap(ticker: str) -> float:
    try:
        info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
        mkt_cap = info.get("marketCap")
        if mkt_cap:
            mkt_cap = float(mkt_cap)
            return mkt_cap
    except Exception as e:
        print(f"[{ticker}] yfinance info failed: {e}")

    try:
        info   = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
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

async def get_current_equity_price(ticker: str) -> float:
    try:
        info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
        price = (info.get("regularMarketPrice"))
        if price:
            price = float(price)
            return price
    except Exception as e:
        print(f"[{ticker}] yfinance info failed: {e}")

    print(f"[{ticker}] Price: unavailable")
    return None

async def get_market_intel_ratios(ticker : str) -> list:

    risk_free_rate = await get_risk_free_rate()
    gnp_deflator   = await get_gnp_deflator()
    hist_vol    = await compute_hist_vol_252d(ticker)
    market_cap  = await get_market_cap(ticker)
    equity_price = await get_current_equity_price(ticker)

    metrics = {
        "risk_free_rate"                    : risk_free_rate,
        "gnp_deflator"                      : gnp_deflator,
        "historical_equity_volatility_252d" : hist_vol,
        "market_cap"                        : market_cap,
        "current_equity_price"              : equity_price,
    }

    return {"metrics" : metrics}
