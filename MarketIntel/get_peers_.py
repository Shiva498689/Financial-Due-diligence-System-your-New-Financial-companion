# pip install edgartools groq yfinance scikit-learn pandas numpy python-dotenv
import argparse
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv
from edgar import Company, set_identity
from groq import Groq
from sklearn.preprocessing import StandardScaler

load_dotenv()

# Initialising the basic variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
EDGAR_IDENTITY = os.getenv("EDGAR_IDENTITY", "user@example.com")

CHUNK_SIZE = 50_000
CHUNK_OVERLAP = 2_000
LLM_TEMPERATURE = 0.0

BIZ_DESC_CHARS = 10_000

YFINANCE_METRICS = {
    "market_cap":       "marketCap",
    "revenue":          "totalRevenue",
    "ebitda":           "ebitda",
    "gross_margin":     "grossMargins",
    "operating_margin": "operatingMargins",
    "profit_margin":    "profitMargins",
    "revenue_growth":   "revenueGrowth",
    "roe":              "returnOnEquity",
    "debt_to_equity":   "debtToEquity",
    "beta":             "beta",
}


SIZE_METRICS = ["market_cap", "revenue", "ebitda"]
# Default weights (used only if LLM weight-tuning fails)
DEFAULT_WEIGHTS = {
    "market_cap": 0.10, "revenue": 0.10, "ebitda": 0.05,
    "gross_margin": 0.15, "operating_margin": 0.15, "profit_margin": 0.10,
    "revenue_growth": 0.15, "roe": 0.10, "debt_to_equity": 0.05,
    "beta": 0.05,
}

# LLM prompts 

# 1. Prompt to extract competitors from 10K filings

EXTRACT_SYSTEM = """\
You are an expert financial analyst. Extract competitor and peer company \
names from SEC 10-K filing text.
RULES:
1. Extract ONLY companies mentioned as COMPETITORS, RIVALS, or PEERS.
2. For EACH competitor provide company_name (full canonical name) and \
ticker (stock symbol — use your financial knowledge even if not stated).
3. DO NOT include customers, suppliers, partners, subsidiaries, \
regulators, or vague references.
4. CONSOLIDATE duplicates (e.g. "Google" + "Alphabet" → one entry).
5. Return ONLY valid JSON.\
"""
EXTRACT_USER = """\
Below is text from the "{section_title}" section of {company_name}'s \
({ticker}) 10-K filing.
Extract ALL competitors/peers. Return JSON:
{{"competitors": [{{"company_name": "string", "ticker": "string or null"}}]}}
If none: {{"competitors": []}}
--- TEXT ---
{text}
--- END ---\
"""


# 2. Prompt to get the peers form broader universe 

BIZMODEL_SYSTEM = """\
You are an expert financial analyst and industry researcher. \
You will be given a company's business description from its SEC 10-K filing. \
Your task is to identify publicly traded companies that share a SIMILAR \
BUSINESS MODEL — even if they are in different industries or SIC codes.
Focus on:
  • Revenue model (subscription, transactional, licensing, ad-supported, etc.)
  • Customer type (B2B, B2C, enterprise, SMB, government, etc.)
  • Value chain position (platform, manufacturer, distributor, service provider)
  • Competitive moat type (network effects, IP, scale, brand, switching costs)
  • Margin & capital intensity profile
Cast a WIDE net — include companies from adjacent industries, \
different geographies, and different scale if the business model is similar.
Return ONLY valid JSON.\
"""
BIZMODEL_USER = """\
Below is the business description of **{company_name}** ({ticker}).
Identify 20-25 publicly traded companies with the MOST SIMILAR business \
model. Include companies from ANY industry — do NOT restrict to the same \
sector/SIC code.
Return JSON:
{{"peers": [{{"company_name": "string", "ticker": "string"}}]}}
--- BUSINESS DESCRIPTION ---
{text}
--- END ---\
"""

# 3. Prompt to fine tune the weights according to the LLM , to decide what importance to give to the various financial metrics of a peer

WEIGHTS_SYSTEM = """\
You are a quantitative equity analyst. Given a company's financial profile, \
assign weights for peer-comparison scoring.
The weights determine which financial metrics matter most when identifying \
the closest comparable company. Your weights MUST reflect this company's \
specific characteristics:
  • High-growth company → weight revenue_growth, gross_margin higher
  • Mature/value company → weight operating_margin, profit_margin, roe higher
  • Capital-intensive/leveraged → weight debt_to_equity, ebitda higher
  • Volatile/cyclical → weight beta higher
  • Large-cap stable → weight market_cap, revenue higher
Return ONLY valid JSON.\
"""
WEIGHTS_USER = """\
Company: {company_name} ({ticker})
Financial Profile:
  Market Cap:       ${market_cap}
  Revenue:          ${revenue}
  EBITDA:           ${ebitda}
  Gross Margin:     {gross_margin}
  Operating Margin: {operating_margin}
  Profit Margin:    {profit_margin}
  Revenue Growth:   {revenue_growth}
  ROE:              {roe}
  Debt/Equity:      {debt_to_equity}
  Beta:             {beta}
Assign weights to these 10 metrics for finding the most comparable peer. \
Weights MUST sum to 1.0. Return JSON:
{{"weights": {{"market_cap": 0.xx, "revenue": 0.xx, "ebitda": 0.xx, \
"gross_margin": 0.xx, "operating_margin": 0.xx, "profit_margin": 0.xx, \
"revenue_growth": 0.xx, "roe": 0.xx, "debt_to_equity": 0.xx, \
"beta": 0.xx}}}}\
"""

# To get the validated ticker from a company name extracted from either sec / LLM

class TickerResolver:
    """
    Resolves company names to validated stock tickers using:
      1. SEC company_tickers.json (13 000+ entries)
      2. Fuzzy name matching (difflib SequenceMatcher)
      3. yfinance search API (fallback for international / non-SEC)
    No hardcoded suffix list — fuzzy matching naturally handles
    "Inc", "Corp", "Ltd", "AG", "SA", "Plc", etc.
    """
    def __init__(self):
        self.name_to_ticker: dict[str, str] = {}  # UPPERCASE name → ticker
        self.ticker_set: set[str] = set()          # all valid tickers
        self._loaded = False
    def load_sec_database(self):
        """Download SEC company_tickers.json and build lookups."""
        import requests
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": f"PeerFinder {EDGAR_IDENTITY}"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for entry in data.values():
                ticker = entry["ticker"].upper()
                name = entry["title"].upper().strip()
                self.ticker_set.add(ticker)
                self.name_to_ticker[name] = ticker
            self._loaded = True
            print(f"    Loaded {len(self.ticker_set):,} tickers from SEC database")
        except Exception as e:
            print(f"    ⚠ Could not load SEC tickers: {e}")
    def _fuzzy_score(self, a: str, b: str) -> float:
        """SequenceMatcher ratio between two strings."""
        return SequenceMatcher(None, a, b).ratio()
    def _fuzzy_match_name(self, query_name: str, cutoff: float = 0.65) -> str | None:
        """
        Find the best fuzzy match for a company name in the SEC database.
        Uses a two-pass approach for speed:
          Pass 1: check names starting with the same first word (fast)
          Pass 2: full scan if pass 1 fails (slower but thorough)
        """
        query = query_name.upper().strip()
        # Exact match
        if query in self.name_to_ticker:
            return self.name_to_ticker[query]
        # Pass 1: names sharing the first word (fast subset)
        first_word = query.split()[0] if query.split() else ""
        if len(first_word) >= 3:
            candidates = {
                k: v for k, v in self.name_to_ticker.items()
                if k.startswith(first_word)
            }
            if candidates:
                best_name = max(candidates, key=lambda k: self._fuzzy_score(query, k))
                score = self._fuzzy_score(query, best_name)
                if score >= cutoff:
                    return candidates[best_name]
        # Pass 2: full scan (only if pass 1 failed and query is long enough)
        if len(query) >= 5:
            best_name = None
            best_score = 0.0
            for name, ticker in self.name_to_ticker.items():
                # Quick pre-filter: skip if first chars differ too much
                if abs(len(name) - len(query)) > max(len(query), len(name)) * 0.5:
                    continue
                score = self._fuzzy_score(query, name)
                if score > best_score:
                    best_score = score
                    best_name = name
            if best_score >= cutoff and best_name:
                return self.name_to_ticker[best_name]
        return None
    def _yfinance_search(self, query: str) -> str | None:
        """Last resort: search via yfinance API."""
        try:
            results = yf.Search(query, enable_fuzzy_query=True)
            if hasattr(results, "quotes") and results.quotes:
                for q in results.quotes:
                    qt = q.get("quoteType", "")
                    if qt in ("EQUITY", "ETF", ""):
                        return q["symbol"]
        except Exception:
            pass
        return None
    def resolve(self, company_name: str, llm_ticker: str | None) -> str | None:
        """
        Resolve a (company_name, llm_ticker) pair to a validated ticker.
        Priority:
          1. LLM ticker if it exists in SEC DB → trust it
          2. Exact name match in SEC DB
          3. Fuzzy name match in SEC DB
          4. LLM ticker validated via yfinance (for international stocks)
          5. yfinance search by company name
        """
        if not self._loaded:
            self.load_sec_database()
        # 1. LLM-provided ticker in SEC database → trust it
        if llm_ticker:
            t = llm_ticker.upper().strip()
            if t in self.ticker_set:
                return t
        # 2 & 3. Exact + fuzzy match against SEC names
        matched = self._fuzzy_match_name(company_name)
        if matched:
            return matched
        # 4. LLM ticker not in SEC DB → might be international; validate via yfinance
        if llm_ticker:
            try:
                info = yf.Ticker(llm_ticker).info
                if info and info.get("marketCap"):
                    return llm_ticker.upper().strip()
            except Exception:
                pass
        # 5. yfinance search as last resort
        found = self._yfinance_search(company_name)
        return found


# chunk text to maintain LLM token limit
def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks — nothing is truncated."""
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks

# groq call
def groq_json_call(
    client: Groq, model: str,
    system: str, user: str,
) -> dict | None:
    """Make a Groq chat call expecting JSON output."""
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=LLM_TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"      ⚠ Groq call failed: {e}")
        return None

def fmt_metric(val, is_pct=False, is_money=False):
    """Format a metric value for display."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    if is_money:
        if abs(val) >= 1e12:
            return f"{val/1e12:.1f}T"
        if abs(val) >= 1e9:
            return f"{val/1e9:.1f}B"
        if abs(val) >= 1e6:
            return f"{val/1e6:.1f}M"
        return f"{val:,.0f}"
    if is_pct:
        return f"{val*100:.1f}%" if abs(val) < 1 else f"{val:.1f}%"
    return f"{val:.2f}"

# Dictionary mapping to extract section from the sec 10K filings

SECTIONS_CONFIG = {
    "1":  {"title": "Business Description",
           "keys": ["Item 1"], "attrs": ["business"]},
    "1A": {"title": "Risk Factors",
           "keys": ["Item 1A"], "attrs": ["risk_factors"]},
    "7":  {"title": "Management Discussion & Analysis",
           "keys": ["Item 7"], "attrs": ["management_discussion", "mda"]},
}

# To extract the various sections from the 10K filings

def _get_section_text(tenk, config: dict) -> str | None:
    """Try bracket-style, then attribute-style access on TenK object."""
    for key in config["keys"]:
        try:
            obj = tenk[key]
            if obj is not None:
                txt = str(obj.text) if hasattr(obj, "text") else str(obj)
                if len(txt.strip()) > 100:
                    return txt.strip()
        except (KeyError, TypeError, IndexError, AttributeError):
            pass
    for attr in config["attrs"]:
        try:
            val = getattr(tenk, attr, None)
            if val is not None:
                txt = str(val.text) if hasattr(val, "text") else str(val)
                if len(txt.strip()) > 100:
                    return txt.strip()
        except Exception:
            pass
    return None


def fetch_filing_sections(ticker: str) -> tuple[str, dict[str, str]]:
    """
    Fetch the latest 10-K and extract section texts.
    Returns (company_name, {item_number: text}).
    """
    print(f"\n  Looking up {ticker} ...")
    company = Company(ticker.upper())
    company_name = company.name
    print(f"  Company:  {company_name}")
    filing = company.get_filings(form="10-K").latest(1)
    if isinstance(filing, list):
        filing = filing[0]
    print(f"  Filed:    {getattr(filing, 'filing_date', 'unknown')}")
    tenk = filing.obj()
    print(f"  Parsed TenK ✓")
    sections: dict[str, str] = {}
    for item_num, cfg in SECTIONS_CONFIG.items():
        text = _get_section_text(tenk, cfg)
        if text:
            sections[item_num] = text
            print(f"  Item {item_num:<3} ({cfg['title']:<40}): ✓ {len(text):>8,} chars")
        else:
            print(f"  Item {item_num:<3} ({cfg['title']:<40}): ✗ not found")
    return company_name, sections


# STEP 1: Extract competitors from the sec1  filing using the prompt , LLM and the fetched sections

def step1_extract_competitors(
    ticker: str, company_name: str,
    sections: dict[str, str],
    client: Groq, model: str,
) -> list[tuple[str, str | None]]:
    """
    Extract competitor (name, ticker) pairs from 10-K sections.
    Chunks long sections so the ENTIRE text is processed.
    Returns raw (name, llm_ticker) pairs — NOT yet validated.
    """
    print("\n" + "─" * 62)
    print("  STEP 1: Extracting competitors from 10-K sections")
    print("─" * 62)
    all_pairs: list[tuple[str, str | None]] = []
    for item_num, text in sections.items():
        title = SECTIONS_CONFIG[item_num]["title"]
        chunks = chunk_text(text)
        print(f"\n  Item {item_num} — {title}: {len(chunks)} chunk(s)")
        for ci, chunk in enumerate(chunks, 1):
            print(f"    chunk {ci}/{len(chunks)} ({len(chunk):,} ch) … ", end="", flush=True)
            prompt = EXTRACT_USER.format(
                section_title=title, company_name=company_name,
                ticker=ticker, text=chunk,
            )
            parsed = groq_json_call(client, model, EXTRACT_SYSTEM, prompt)
            if parsed:
                comps = parsed.get("competitors", [])
                for c in comps:
                    name = c.get("company_name", "").strip()
                    t = c.get("ticker")
                    if name:
                        all_pairs.append((name, t))
                print(f"{len(comps)} found")
            else:
                print("failed")
            time.sleep(0.3)
    print(f"\n  ➜ Raw extractions: {len(all_pairs)} (name, ticker) pairs")
    return all_pairs

# STEP 2 : using LLM to get peers with similar business model irrespective of the SIC code , industry 
def step2_business_model_peers(
    ticker: str, company_name: str,
    sections: dict[str, str],
    client: Groq, model: str,
) -> list[tuple[str, str | None]]:
    """
    Ask the LLM to suggest companies with a similar BUSINESS MODEL,
    using the business description (Item 1). This is far broader than
    SIC codes — it captures cross-industry peers.
    """
    print("\n" + "─" * 62)
    print("  STEP 2: Finding business-model peers via LLM")
    print("─" * 62)
    # Use Item 1 (business description) as the source
    biz_text = sections.get("1", "")
    if not biz_text:
        # Fall back to any available section
        biz_text = next(iter(sections.values()), "")
    if not biz_text:
        print("  ⚠ No business description available. Skipping.")
        return []
    # Send a representative portion (first N chars)
    text_to_send = biz_text[:BIZ_DESC_CHARS]
    print(f"  Sending {len(text_to_send):,} chars of business description to LLM …")
    prompt = BIZMODEL_USER.format(
        company_name=company_name, ticker=ticker, text=text_to_send,
    )
    parsed = groq_json_call(client, model, BIZMODEL_SYSTEM, prompt)
    pairs: list[tuple[str, str | None]] = []
    if parsed:
        for p in parsed.get("peers", []):
            name = p.get("company_name", "").strip()
            t = p.get("ticker")
            if name:
                pairs.append((name, t))
    print(f"  ➜ LLM suggested {len(pairs)} business-model peers")
    return pairs

# Function to get a clean list of tickers (no company names , only tickers) , no hallucinated tickers , no duplication

def step3_validate_tickers(
    all_pairs: list[tuple[str, str | None]],
    target_ticker: str,
    resolver: TickerResolver,
) -> list[str]:
    """
    Validate and resolve all (name, llm_ticker) pairs to real tickers.
    Deduplicates by resolved ticker. Removes the target itself.
    """
    print("\n" + "─" * 62)
    print("  STEP 3: Validating & resolving tickers")
    print("─" * 62)
    resolved: dict[str, str] = {}   # resolved_ticker → first company name seen
    failed: list[str] = []
    for name, llm_ticker in all_pairs:
        t = resolver.resolve(name, llm_ticker)
        if t and t.upper() != target_ticker.upper():
            if t.upper() not in resolved:
                resolved[t.upper()] = name
        else:
            if name not in failed:
                failed.append(name)
    tickers = sorted(resolved.keys())
    print(f"  ✓ Resolved: {len(tickers)} unique tickers")
    if tickers:
        for t in tickers:
            print(f"    {t:<8s} ← {resolved[t]}")
    if failed:
        print(f"  ✗ Could not resolve: {failed[:10]}")
    return tickers

# STEP 4 : Fetching the financial features defined before for the list of peers obtained from the validate ticker list

def step4_collect_financials(
    target_ticker: str,
    peer_tickers: list[str],
) -> pd.DataFrame:
    """Pull financial data for target + all peers via yfinance."""
    print("\n" + "─" * 62)
    print("  STEP 4: Collecting financial data (yfinance)")
    print("─" * 62)
    all_tickers = [target_ticker.upper()] + peer_tickers
    rows = []
    for i, t in enumerate(all_tickers, 1):
        print(f"  [{i:>2}/{len(all_tickers)}] {t:<8s}… ", end="", flush=True)
        try:
            info = yf.Ticker(t).info
            if not info or not info.get("marketCap"):
                print("✗ no data")
                continue
            row = {"ticker": t}
            for our_key, yf_key in YFINANCE_METRICS.items():
                row[our_key] = info.get(yf_key)
            rows.append(row)
            mc = fmt_metric(info.get("marketCap"), is_money=True)
            print(f"✓  (mktcap: {mc})")
        except Exception as e:
            print(f"✗ error: {e}")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("ticker")
    for col in YFINANCE_METRICS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    print(f"\n  ➜ Got data for {len(df)} / {len(all_tickers)} tickers")
    return df

# STEP 5 : Preprocess the festures to add log proprotionality to make sure that the (1 B is not the same as 0.5T while 3T is not the same as 2T)

def step5_engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Log-transform sizes, fill NaN with median, StandardScaler."""
    print("\n" + "─" * 62)
    print("  STEP 5: Engineering features (sklearn)")
    print("─" * 62)
    features = df.copy()
    for col in SIZE_METRICS:
        if col in features.columns:
            features[col] = np.log1p(features[col].clip(lower=0))
    for col in features.columns:
        n_miss = features[col].isna().sum()
        if n_miss > 0:
            med = features[col].median()
            features[col] = features[col].fillna(med)
            print(f"    filled {n_miss} NaN in '{col}' with median")
    scaler = StandardScaler()
    scaled = pd.DataFrame(
        scaler.fit_transform(features),
        index=features.index, columns=features.columns,
    )
    print(f"  ➜ Scaled feature matrix: {scaled.shape}")
    return scaled

# TO GET THE DYNAMIC WEIGHTS (dpeending on the comapny ) by passing the target company info and then normalising the weights such that they sum up to 1 
def _get_dynamic_weights(
    target_ticker: str,
    company_name: str,
    raw_df: pd.DataFrame,
    client: Groq, model: str,
) -> dict[str, float]:
    """
    Ask the LLM to assign feature weights based on the target's
    actual financial profile. Falls back to defaults on failure.
    """
    print("\n  Tuning weights via LLM …")
    if target_ticker not in raw_df.index:
        print("    ⚠ No financial data for target. Using default weights.")
        return DEFAULT_WEIGHTS
    row = raw_df.loc[target_ticker]
    prompt = WEIGHTS_USER.format(
        company_name=company_name, ticker=target_ticker,
        market_cap=fmt_metric(row.get("market_cap"), is_money=True),
        revenue=fmt_metric(row.get("revenue"), is_money=True),
        ebitda=fmt_metric(row.get("ebitda"), is_money=True),
        gross_margin=fmt_metric(row.get("gross_margin"), is_pct=True),
        operating_margin=fmt_metric(row.get("operating_margin"), is_pct=True),
        profit_margin=fmt_metric(row.get("profit_margin"), is_pct=True),
        revenue_growth=fmt_metric(row.get("revenue_growth"), is_pct=True),
        roe=fmt_metric(row.get("roe"), is_pct=True),
        debt_to_equity=fmt_metric(row.get("debt_to_equity")),
        beta=fmt_metric(row.get("beta")),
    )
    parsed = groq_json_call(client, model, WEIGHTS_SYSTEM, prompt)
    if parsed and "weights" in parsed:
        w = parsed["weights"]
        # Validate: must have all keys and sum ≈ 1.0
        expected_keys = set(DEFAULT_WEIGHTS.keys())
        if set(w.keys()) >= expected_keys:
            # Normalize to sum to exactly 1.0
            total = sum(w[k] for k in expected_keys)
            if total > 0:
                weights = {k: w[k] / total for k in expected_keys}
                print("    ✓ LLM-assigned weights:")
                for k, v in sorted(weights.items(), key=lambda x: -x[1]):
                    bar = "█" * int(v * 50)
                    print(f"      {k:<20s} {v:.3f}  {bar}")
                return weights
    print("    ⚠ LLM weight tuning failed. Using defaults.")
    return DEFAULT_WEIGHTS

# STEP 6 : calculate the distance netween each of the peers and the target ticker 

def step6_find_best_peer(
    scaled_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    target_ticker: str,
    company_name: str,
    client: Groq, model: str,
) -> str:
    """
    Dynamic weight tuning via LLM + weighted Euclidean distance.
    Returns the best peer ticker.
    """
    print("\n" + "─" * 62)
    print("  STEP 6: Dynamic weight tuning + similarity scoring")
    print("─" * 62)
    target_ticker = target_ticker.upper()
    if target_ticker not in scaled_df.index:
        print(f"  ❌ Target {target_ticker} has no financial data.")
        sys.exit(1)
    # ── Get dynamic weights from LLM ──
    weights = _get_dynamic_weights(
        target_ticker, company_name, raw_df, client, model
    )
    # ── Build weight vector aligned with DataFrame columns ──
    weight_vec = np.array([weights.get(col, 0.05) for col in scaled_df.columns])
    weight_vec = weight_vec / weight_vec.sum()
    target_vec = scaled_df.loc[target_ticker].values
    # ── Compute weighted Euclidean distance ──
    results = []
    for peer in scaled_df.index:
        if peer == target_ticker:
            continue
        diff = target_vec - scaled_df.loc[peer].values
        dist = np.sqrt(np.sum(weight_vec * diff ** 2))
        results.append({"ticker": peer, "distance": dist})
    if not results:
        print("  ❌ No peers to compare.")
        sys.exit(1)
    res_df = pd.DataFrame(results).sort_values("distance")
    max_dist = res_df["distance"].max()
    res_df["similarity"] = (
        ((1 - res_df["distance"] / max_dist) * 100).round(2)
        if max_dist > 0 else 100.0
    )
    # ── Display top 10 ──
    print(f"\n  {'Rank':<6}{'Ticker':<10}{'Distance':<12}{'Similarity':<12}")
    print("  " + "─" * 38)
    for rank, (_, row) in enumerate(res_df.head(10).iterrows(), 1):
        print(
            f"  {rank:<6}{row['ticker']:<10}"
            f"{row['distance']:<12.4f}{row['similarity']:<12.2f}"
        )
    return res_df.iloc[0]["ticker"]

def main():
    parser = argparse.ArgumentParser(
        description="Find the best peer company using SEC 10-K + Groq LLM + financial similarity.",
    )
    parser.add_argument("ticker", help="Target company ticker (e.g. AAPL)")
    parser.add_argument("--model", default=GROQ_MODEL,
                        help=f"Groq model (default: {GROQ_MODEL})")
    parser.add_argument("--groq-key", default=GROQ_API_KEY,
                        help="Groq API key")
    parser.add_argument("--identity", default=EDGAR_IDENTITY,
                        help="Email for SEC EDGAR")
    args = parser.parse_args()
    if not args.groq_key:
        print("\n❌  GROQ_API_KEY required. Set in .env or pass --groq-key.\n")
        sys.exit(1)
    target = args.ticker.upper()
    print("\n╔═══════════════════════════════════════════════════════════╗")
    print(f"║  PEER FINDER v2 — Target: {target:<31s}║")
    print("╚═══════════════════════════════════════════════════════════╝")
    # ── Configure ──
    set_identity(args.identity)
    client = Groq(api_key=args.groq_key)
    resolver = TickerResolver()
    # ── Step 0: Fetch 10-K sections ──
    print("\n" + "─" * 62)
    print("  STEP 0: Fetching 10-K filing (edgartools)")
    print("─" * 62)
    company_name, sections = fetch_filing_sections(target)
    if not sections:
        print("\n❌  Could not extract any sections. Exiting.\n")
        sys.exit(1)
    # ── Step 1: Extract competitors from 10-K ──
    pairs_10k = step1_extract_competitors(
        target, company_name, sections, client, args.model
    )
    # ── Step 2: Business-model peers ──
    pairs_biz = step2_business_model_peers(
        target, company_name, sections, client, args.model
    )
    # ── Step 3: Validate & resolve tickers ──
    print("\n    Loading SEC ticker database …")
    resolver.load_sec_database()
    all_pairs = pairs_10k + pairs_biz
    universe = step3_validate_tickers(all_pairs, target, resolver)
    if not universe:
        print("\n❌  No valid peers found. Exiting.\n")
        sys.exit(1)
    # ── Step 4: Collect financial data ──
    raw_df = step4_collect_financials(target, universe)
    if len(raw_df) < 2:
        print("\n❌  Not enough financial data to compare. Exiting.\n")
        sys.exit(1)
    # ── Step 5: Engineer features ──
    scaled_df = step5_engineer_features(raw_df)
    # ── Step 6: Dynamic weights + similarity ──
    best = step6_find_best_peer(
        scaled_df, raw_df, target, company_name, client, args.model
    )
    # ── Final output ──
    print("\n" + "═" * 56)
    print(f"  🏆  BEST PEER:  {best}")
    print("═" * 56 + "\n")
if __name__ == "__main__":
    main()

