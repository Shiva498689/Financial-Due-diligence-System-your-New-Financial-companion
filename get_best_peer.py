import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import Optional
import asyncio
import aiohttp
import yfinance as yf
from dotenv import load_dotenv
from groq import Groq
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from google import genai
from google.genai import types
import json
from edgar import Company ,  set_identity
set_identity("Nitin jainnitin788@gmail.com")
load_dotenv()

# TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY1')
# GROQ_API_KEY = os.getenv('GROQ_API_KEY')
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY2")
TAVILY_API_KEY="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"
GEMINI_API_KEY ="AQ.Ab8RN6K3NVt8Kfxpu_FBu8yUQ86GZHljcF_n1CJHElD8yJt1gA"
GROQ_API_KEY="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"

# DEFINING
def __len__(x):
        return len(x) if x else 0
CORE_ATTR_KEYS = [
    "products", "customers", "end_markets", "geography",
    "revenue_size", "growth_rate", "margins", "pricing_model",
    "distribution", "public_private", "maturity_stage",
]

LLM_MODEL = "openai/gpt-oss-120b"

QUAL_WEIGHT  = 0.8
QUANT_WEIGHT = 0.2

QUAL_CRITERIA_WEIGHTS = {
    "product_overlap":   0.25,
    "customer_overlap":  0.20,
    "geography":         0.15,
    "business_model":    0.15,
    "scale":             0.10,
    "financial_profile": 0.10,
    "strategic_pos":     0.05,
}

# Quantitative scoring weights
QUANT_METRIC_WEIGHTS = {
    "market_cap":       0.10,
    "revenue":          0.10,
    "ebitda":           0.05,
    "gross_margin":     0.15,
    "operating_margin": 0.15,
    "profit_margin":    0.10,
    "revenue_growth":   0.15,
    "roe":              0.10,
    "debt_to_equity":   0.05,
    "beta":             0.05,
}

CHUNK_SIZE = 20_000
CHUNK_OVERLAP = 1500

# HELPER FUNCTIONS
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split *text* into chunks of approximately *chunk_size* characters
    with *overlap* character overlap.  Returns at least one chunk even if
    text is shorter than chunk_size."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start >= len(text):
            break
    return chunks

async def fetch_text(target_ticker : str) -> str:
    print ('Fetching text from the sec filings....')
    text = ""
    company = await asyncio.to_thread(Company, target_ticker)
    filing = await asyncio.to_thread(lambda: company.get_filings(form="10-K").latest())
    tenk = await asyncio.to_thread(lambda: filing.obj())
    text += (str(tenk['Item 1']))
    text += (str(tenk['Item 1A']))
    proxy_statement = await asyncio.to_thread(lambda: company.get_filings(form = "DEF 14A").latest())
    text += await asyncio.to_thread(lambda: str(proxy_statement.text()))
    return text

# EXTRACTING COMPANY NAMES FROM THE GIVEN SEC FILINGS
async def stage_ner_gemini(text: str, model: str = "gemini-3.5-flash-lite") -> list[str]:
    """
    Extract publicly traded company names from SEC filing text using Gemini 3.1 flash lite.
    Returns deduplicated list of company names (NOT tickers).
    """
    print("STEP 2: Extracting company names via Gemini 3.1 Flash lite")
    MAX_CHARS_PER_CHUNK = 249_000  # Conservative: ~100K tokens
    chunks = chunk_text(text , MAX_CHARS_PER_CHUNK , 100)
    client = genai.Client(api_key = GEMINI_API_KEY)
    all_names = set()
    system_prompt = """You are a financial document analyst extracting company names from SEC filings.
TASK: Read the provided SEC filing text and extract ALL unique company names mentioned.
Include:
- Competitors named in "Competition" or "Risk Factors" sections
- Companies in "Selected Financial Data" or "Management's Discussion"
- Named in legal proceedings, partnerships, or acquisitions
- Parent companies and significant subsidiaries
EXCLUDE:
- The filing company itself (the issuer)
- Law firms, audit firms, consulting firms (e.g., "Deloitte", "Skadden Arps")
- Government agencies (e.g., "SEC", "FDA", "IRS")
- Stock exchanges (e.g., "NASDAQ", "NYSE")
- Generic terms like "the Company", "our competitors", "industry participants"
- Individuals and person names
OUTPUT FORMAT: Return ONLY a JSON array of strings. No explanations, no markdown.
Example: ["Samsung Electronics", "Microsoft Corporation", "Alphabet Inc"]
ACCURACY RULES:
- Use full legal names when available (e.g., "Microsoft Corporation" not just "Microsoft")
- Preserve exact spelling from the text
- Include both domestic and international companies
- If a company has multiple name variants, include the most complete form"""

    for i, chunk in enumerate(chunks, 1):
        print(f"  Processing chunk {i}/{len(chunks)} ({len(chunk):,} chars)...")
        user_prompt = f"""SEC Filing Text:{chunk}
        Extract all company names as a JSON array."""


        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=system_prompt),
                            types.Part(text=user_prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                ),
            )

            raw = response.text.strip()
            names = json.loads(raw)

            for name in names:
              all_names.add(name)

        except json.JSONDecodeError as e:
            print(f"    JSON parse error chunk {i}: {e}")
            # Fallback: extract lines that look like array items
            raw_lines = [l.strip().strip('"[],') for l in raw.split('\n') if l.strip()]
            for line in raw_lines:
                if line and not line.startswith('[') and not line.endswith(']'):
                    all_names.add(line)

        except Exception as e:
            print(f"API error chunk {i}: {e}")

    result = sorted(list(all_names))
    print(f"  Total unique company names extracted: {len(result)}")
    return result

# Step 1 -> LOOK for the competitor names in the given sec text
async def stage_llm_resolution(
    target_ticker: str,
    candidates: list[str],
) -> list[str]:
    print(
        "STEP 2: Using LLM to identify competitors "
        f"{target_ticker.upper()}"
    )

    if not candidates:
        return []

    target_ticker = target_ticker.strip().upper()

    # Normalize and deduplicate candidate names.
    cleaned_candidates = []
    seen = set()

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue

        name = " ".join(candidate.split()).strip()
        key = name.casefold()

        if name and key not in seen:
            cleaned_candidates.append(name)
            seen.add(key)

    if not cleaned_candidates:
        return []

    system = f"""You are a financial competitive-intelligence analyst.
Target company ticker: {target_ticker}
The candidate list may contain company names, legal company names, existing
tickers, products, regulators, universities, committees, suppliers, customers,
and other entities.
Your task is:
1. Resolve candidate company names to publicly traded stock tickers.
2. Identify which resolved companies compete with {target_ticker} in at least
   one meaningful product or service segment.
A company qualifies as a competitor if it offers a substantially similar
product or service, serves overlapping customers, or competes for the same
clearly defined market need.
Include a candidate if it competes with the target in at least one meaningful product, service, customer, geographic, or use-case segment , even if the candidate operates in a different overall industry.
The candidate competes with the target across multiple major products,
   services, or strategic ecosystem areas.
The candidate competes for the same customer budget, attention, platform,
   or ecosystem but does not offer a substantially similar product or service.
A company may be a segment competitor even if it does not compete with the
target's entire business.
Exclude:
- the target company itself;
- products and brands;
- regulators and government bodies;
- universities and courts;
- committees and individuals;
- suppliers and manufacturers;
- customers and partners;
- compensation peers with no product overlap;
- unrelated companies;
- private, ambiguous, or unresolvable companies.
Rules:
- Select only companies represented by the supplied candidate list.
- Do not invent a company that is absent from the candidate list.
- Company names must be resolved to tickers before being returned.
- Use international exchange suffixes when required.
- Use uppercase tickers.
- If a company has multiple share classes, use the primary commonly traded
  ticker.
- Prefer precision over recall.
Return ONLY this valid JSON object:
{{"competitors": ["TICKER1", "TICKER2"]}}

Do not return Markdown.
Do not return explanations.
If no candidate qualifies, return:
{{"competitors": []}}"""

    user_msg = json.dumps(
        {
            "target_ticker": target_ticker,
            "candidate_entities": cleaned_candidates,
        },
        ensure_ascii=False,
    )

    if True:
        raw_content = ""

        try:
            groq_client = Groq(api_key = GROQ_API_KEY)
            resp = await asyncio.to_thread(
                groq_client.chat.completions.create,
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=3000,
            )

            if not resp.choices:
                raise ValueError("LLM response contained no choices")

            raw_content = resp.choices[0].message.content or ""

            print("RAW LLM RESPONSE:")
            raw_content = json.loads(raw_content)
            parsed_tickers = (raw_content).get("competitors" , [])

        except Exception as exc:
            print(f"LLM Error: {type(exc).__name__}: {exc}")
            print(f"Raw Output was: {raw_content.get('competitors')}")
            return []

    # Remove the target itself and deduplicate.
    competitor_tickers = []
    seen_tickers = set()

    for ticker in parsed_tickers:
        ticker = ticker.strip().upper()

        if not ticker or ticker == target_ticker:
            continue

        if ticker not in seen_tickers:
            competitor_tickers.append(ticker)
            seen_tickers.add(ticker)

    print(f"Final competitor tickers: {competitor_tickers}")
    return competitor_tickers

# Helper function to get competitor attributes
async def fetch_sec_comp_attrs(ticker : str) -> str:
  text = ""
  tenk = await asyncio.to_thread(lambda: Company(ticker).get_filings(form = "10-K").latest().obj())
  text += (str(tenk['Item 1']))[:5000]
  text += (str(tenk['Item 1A']))[:5000]
  return text

# Function to obtain core sttributes of any given ticker
async def get_core_attr(ticker: str, max_results: int = 4) -> dict:
    """
    Fetch core business attributes for any ticker using web search + Gemini.
    Uses Google GenAI SDK (google-genai) - the current recommended SDK.
    """
    print(f"═══ Fetching core attributes for {ticker} ═══")

    # --- 1. Tavily Web Search ---
    queries = {
        "basic": f"{ticker} company profile, products, target customers, geography, distribution channels, business model",
        "advanced": f"{ticker} annual revenue, year-over-year revenue growth rate, gross margin, operating margin financial metrics"
    }

    evidence = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        for depth, query_text in queries.items():
            async with session.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query_text,
                    "search_depth": depth,
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            ) as resp:
                resp.raise_for_status()
                data = (await resp.json()).get("results", [])

            for result in data:
                evidence.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": (result.get("content", "") or "")[:1500],
                })

    # --- 2. Gemini API Call via Google GenAI SDK ---

    # Initialize client with API key from environment
    # Uses GOOGLE_API_KEY or GEMINI_API_KEY env var
    client = genai.Client(api_key = GEMINI_API_KEY)

    system_prompt = """You are a financial business-profile analyst.

    You receive a ticker symbol and a set of web-search results about the company.
    Your job is to extract the company's core business attributes and return them
    as a single valid JSON object.

    Use only the information supported by the supplied search results. Do not
    invent facts. If an attribute cannot be determined from the evidence, return
    null for that attribute.

    Return ONLY valid JSON. Do not use Markdown. Do not include explanations.
    """

    user_prompt = f"""Ticker: {ticker}

    Required JSON keys (exactly these):
    {json.dumps(CORE_ATTR_KEYS, indent=2)}

    Guidance for each key:
    - products: list of main products or services.
    - customers: main customer groups or end users.
    - end_markets: industries or markets served.
    - geography: main geographic regions of operation.
    - revenue_size: approximate annual revenue in USD with units (e.g., "394B USD").
    - growth_rate: approximate year-over-year revenue growth percentage.
    - margins: approximate gross and operating margin percentages.
    - pricing_model: how the company charges (subscription, transaction, wholesale, etc.).
    - distribution: main sales and distribution channels.
    - public_private: "public" or "private".
    - maturity_stage: one of early_stage, growth, mature, or declining, with brief justification.

    Web-search evidence:
    {json.dumps(evidence, indent=2, ensure_ascii=False)}

    Return a single JSON object with the keys above.
    """

    # Gemini API call using GenAI SDK
    # Model options: gemini-2.5-flash, gemini-2.5-pro, gemini-3.5-flash, gemini-3.5-pro, etc.
    response = await client.aio.models.generate_content(
        model="gemini-3.1-flash-lite",  # or "gemini-3.5-flash" for newer models
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(text=system_prompt),
                    types.Part(text=user_prompt),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=3000,
            response_mime_type="application/json",
        ),
    )

    # Extract and parse JSON
    raw_content = response.text
    core_attrs = json.loads(raw_content)

    return core_attrs

# STEP 2A : extract target atrributes (competitor + core)
async def step_2a_target_attributes(ticker: str) -> tuple[str, dict]:
    """"Extract competitive landscape from 10-K chunks, and core attributes via web search.
    Returns (competitor_attrs_str, core_attrs_dict)."""
    text = await fetch_sec_comp_attrs(ticker)

    # Truncate each section to first 5K chars (attributes in opening paragraphs)
    competitor_attrs = ""
    system_prompt = f"""
You are a financial filings analyst specializing in competitive intelligence.
Analyze the supplied text from a company's SEC filing and extract the
company's competitive landscape and business attributes.
YOUR TASK:
Extract the following categories of information from the filing text.
1. COMPETITIVE FACTORS
   The dimensions on which the company says it competes.
   Examples: pricing, product quality, reliability, innovation, brand
   reputation, ecosystem integration, speed of delivery, regulatory
   expertise, scale, intellectual property, customer service, distribution
   reach, switching costs, network effects.
   Extract only factors explicitly stated or strongly implied by the text.
2. PRODUCTS AND SERVICES
   The company's own offerings, preserving its business categories at a
   meaningful level of detail.
   Do NOT collapse distinct product lines into a single generic label.
   For example, list "smartphones, personal computers, tablets, wearables,
   streaming subscriptions" rather than just "technology products."
3. CUSTOMER SEGMENTS
   Who buys from the company: consumers, enterprises, SMBs, governments,
   developers, healthcare providers, financial institutions, etc.
4. MARKETS AND USE CASES
   The industries, verticals, or specific use cases the company serves.
   For example: "mobile payments, digital advertising, cloud computing,
   autonomous vehicles, oncology therapeutics."
5. GEOGRAPHIES
   Regions or countries explicitly mentioned as markets.
6. BUSINESS MODEL
   How the company generates revenue: hardware sales, software licensing,
   subscriptions, advertising, transaction fees, royalties, etc.
7. CAPABILITIES AND ADVANTAGES
   Assets or capabilities that create competitive advantage: proprietary
   technology, patents, manufacturing scale, supply chain control, data
   assets, regulatory approvals, installed base, talent, R&D investment.
9. NON-COMPETITORS MENTIONED
   Suppliers, partners, customers, regulators, investors, board members,
   or compensation peers that appear in the text but must NOT be confused
   with competitors.
RULES:
- Use ONLY information supported by the supplied filing text.
- Do NOT use your own knowledge to infer competitors or attributes.
- Do NOT treat every company mentioned in the filing as a competitor.
- If a category has no supporting evidence in the text, return an empty list.
Return exactly this structure:
{{
  "competitive_factors": [],
  "products_and_services": [],
  "customer_segments": [],
  "markets_and_use_cases": [],
  "geographies": [],
  "business_model": [],
  "capabilities_and_advantages": [],
  "named_competitors": [],
  "non_competitors": []
}}
"""

    user_msg = f"Text : {text}"
    groq_client = Groq(api_key = GROQ_API_KEY)
    resp = await asyncio.to_thread(
        groq_client.chat.completions.create,
        model = LLM_MODEL ,
        messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
        temperature=0.0,
        max_tokens=1500,
    )
    competitor_attrs = resp.choices[0].message.content

    if not competitor_attrs:
        competitor_attrs = "The company faces intense competition in all major markets."

    print(f"  Competitor description extracted from 10-K: {len(competitor_attrs)} ")

    print("  Fetching core attributes via web search ...")
    core_attrs = await get_core_attr(ticker)

    return competitor_attrs , core_attrs

# STEP 2B : GET COMPETITOR COMPANIES VIA WEB SEARCH GIVING COMPETITOR ATTRIBUTES AS THE INPUT
async def step_2b_discover_suspects(target_ticker: str , competitor_attrs: str, core_attrs : dict, known_peers: list[str]) -> list[str]:
    """Use Groq compound-beta with web search to find additional suspect peers."""

    known_str = ""

    if known_peers:
        known_str = ", ".join(known_peers[:15])
        if len(known_peers) > 15:
            known_str += f" (and {len(known_peers) - 15} others)"
    else:
        known_str = "none yet"

    raw_products = core_attrs.get("products") or []
    raw_markets = core_attrs.get("end_markets") or []
    raw_customers = core_attrs.get("customers") or []

    if isinstance(raw_products, str): raw_products = [raw_products]
    if isinstance(raw_markets, str): raw_markets = [raw_markets]
    if isinstance(raw_customers, str): raw_customers = [raw_customers]

    products = ", ".join(raw_products[:5])
    end_markets = ", ".join(raw_markets[:5])
    customers = ", ".join(raw_customers[:3])

    search_query = (
        f"{target_ticker} competitors "
        f"{products} {end_markets} {customers} "
        f"publicly traded companies"
    )

    search_query = search_query[:400]

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": search_query,
                "search_depth": "advanced",
                "max_results": 3,
                "include_answer": False,
                "include_raw_content": False,
            },
        ) as resp:
            resp.raise_for_status()
            peers = (await resp.json()).get("results" , [])

    evidence = json.dumps(peers, indent=2, ensure_ascii=False)
    print (evidence)

    system_prompt = """
You are a financial competitive-intelligence analyst.

You receive a target company ticker, a description of its competitive
landscape, and web-search results. Your job is to identify publicly traded
companies that compete with the target in its core markets.

Rules:
- Return ONLY a JSON array of ticker symbols.
- Do not include company names, explanations, or Markdown.
- Do not return multiple tickers for the same company.
- Prefer primary listed tickers.
- Include international or OTC tickers only if they are valid Yahoo Finance tickers.
- Exclude suppliers, component manufacturers, customers, partners, and unrelated companies.
- Exclude companies already listed as known peers.
- If no suitable competitors are found, return [].
"""

    user_prompt = (
        f"Target ticker: {target_ticker}\n\n"
        f"Competitive landscape:\n{competitor_attrs[:4000]}\n\n"
        f"Known peers to exclude: {known_str}\n\n"
        f"Web-search evidence:\n{evidence}\n\n"
        "Return a JSON array of competitor ticker symbols."
    )

    client = Groq(api_key = GROQ_API_KEY)

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=1500,
    )

    raw_content = response.choices[0].message.content

    return raw_content

# FUNCTION TO MERGE THE PEERS FROM SEC DATA AND INDIRECT COMPETITPRS
def merge_peers(target_ticker: str,
                sec_peers : list[str],
                indirect_peers: list[str]) -> list[str]:
    """Deduplicate and combine all discovered peers.
    Returns (all_peers, peer_sources)."""
    print("═══ Merging all peers ═══")

    final_peers : list[str] = []

    for t in indirect_peers:
        if (t.upper() is not target_ticker):
          final_peers.append(t.upper())

    for t in sec_peers:
      if (t.upper() is not target_ticker):
        final_peers.append(t.upper())

    # Final list = filtered direct + indirect, deduplicated
    all_set: set[str] = set()
    for t in final_peers:
        all_set.add(t.upper())
    all_set.discard(target_ticker.upper())

    all_peers = sorted(all_set)
    print(f"  Total unique peers: {len(all_peers)}")

    return all_peers

# LLM CALL TO VALIDATE THE FINAL SIGNIFICANT COMPETITORS
async def validate_competitor(target_ticker: str, candidate_tickers: list[str]) -> list[str]:
    """
    Returns True if candidate is a genuine competitor of target.
    Generalized for any ticker pair.
    """

    system_prompt = """
You are a senior competitive-intelligence analyst.

Your task is to identify genuine competitors of a target company from a
closed list of candidate tickers.

You will receive:
1. The target ticker.
2. A list of candidate tickers.

You must select only from the supplied candidate tickers.

## Core definition

A candidate is a CORE competitor only if it has substantial overlap with at
least one material business segment of the target company.

The overlap must involve at least one of the following:

1. PRODUCT OR SERVICE SUBSTITUTION
   Customers can reasonably choose the candidate's product or service instead
   of the target's product or service to satisfy the same important need.

2. PLATFORM OR ECOSYSTEM RIVALRY
   The candidate operates a competing platform, operating system, ecosystem,
   or network and competes for the same users, developers, customers, or
   strategic position.

3. CORE CUSTOMER AND MARKET OVERLAP
   The candidate sells to substantially the same customer type, in the same
   material market, through a similar business model.

4. DOCUMENTED COMPETITIVE RELATIONSHIP
   Reliable supplied evidence explicitly identifies the candidate as a
   competitor of the target in a material business segment.

## Materiality requirement

Do not classify a candidate as a CORE competitor merely because it overlaps
with:
- a small or non-core product;
- a minor service;
- a single feature;
- general consumer attention;
- a broad industry;
- a distant future possibility;
- an unrelated business segment.

If the target profile does not show that the overlapping segment is material,
exclude the candidate from CORE competitors.

## Exclusions

Exclude candidates that are:
- suppliers;
- component manufacturers;
- infrastructure providers used by the target;
- customers;
- distributors or channel partners;
- regulators;
- investors;
- compensation or financial benchmarking peers;
- companies with only broad industry similarity;
- companies with only a minor or incidental product overlap;
- companies where the evidence is insufficient.

  Important:
  - Select only tickers from the supplied candidate list.
  - Do not invent tickers.
  - Do not modify ticker symbols.
  - Do not include the target ticker.
  - Do not include known peers that are marked for exclusion.
  - If evidence is insufficient, exclude the candidate.
  - Return valid JSON array of validated tickers only.
  - Do not include Markdown or explanations outside the JSON.
  """

    user_prompt = (
        f"Target company: {target_ticker}\n\n"
        f"Candidate tickers to validate:\n{json.dumps(candidate_tickers)}\n\n"
        f"Which of these candidates are genuine competitors of {target_ticker}?"
    )

    client = Groq(api_key = GROQ_API_KEY)

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=3000,
    )

    raw_content = response.choices[0].message.content
    print (raw_content)

    return json.loads(raw_content)

async def get_target_core_attrs(target_ticker : str) -> dict:
  return await get_core_attr(target_ticker)

async def get_peer_attrs_dict(peers_list : list[str]) -> dict[str , dict]:
  peers_attrs_dict : dict[str , dict] = {}

  for peer in peers_list :
    print ("Fetching core atrributes for : " , peer , "......")
    peer_attrs = await get_core_attr(peer)
    peers_attrs_dict[peer] = peer_attrs

  return peers_attrs_dict

# APPLY QUALITATIVE SCORING TO GET THE QUALITATIVE SCORES OF THE SUSPECT COMAPNIES
async def step_4_qualitative_scoring(target_ticker: str,
                                target_core_attrs: dict,
                                peer_attrs_dict: dict[str, dict]) -> dict[str, float]:
    """Score each peer vs the target on 7 qualitative criteria using LLM,
    then apply deterministic weights to compute a final qual_score (0-10)."""
    print("═══ Step 4: Qualitative scoring ═══")
    if not peer_attrs_dict:
        return {}

    target_json = json.dumps(target_core_attrs, indent=2)
    criteria = list(QUAL_CRITERIA_WEIGHTS.keys())
    criteria_str = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(criteria))

    raw_scores: dict[str, dict[str, float]] = {}
    peer_list = list(peer_attrs_dict.keys())

    # Batch 3 at a time
    for i in range(0, len(peer_list), 3):
        batch = peer_list[i:i + 3]
        batch_attrs = {t: peer_attrs_dict[t] for t in batch}
        batch_json = json.dumps(batch_attrs, indent=2)

        system_prompt = (
            "You are an expert financial analyst.  Score each peer company against the "
            "target company on the following criteria, using a scale of 0-10 where:\n"
            "  0 = no similarity/overlap\n"
            "  5 = moderate similarity\n"
            "  10 = nearly identical\n\n"
            f"Criteria:\n{criteria_str}\n\n"
            "Return ONLY a JSON object: {\"TICKER\": {\"criterion\": score, ...}, ...}"
        )
        user_msg = (
            f"Target company: {target_ticker}\n"
            f"Target attributes:\n{target_json}\n\n"
            f"Peer companies to score:\n{batch_json}"
        )

        client = Groq(api_key = GROQ_API_KEY)
        resp = await asyncio.to_thread(
                client.chat.completions.create,
                model = LLM_MODEL ,
                messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_msg},
                        ],
                temperature=0.0,
                max_tokens=1500,
            )
        raw = (resp.choices[0].message.content)

        parsed = json.loads(raw)

        if isinstance(parsed, dict):
            for t, scores in parsed.items():
                if isinstance(scores, dict):
                    # Convert all values to float, default 5 if missing
                    clean = {}
                    for c in criteria:
                        val = scores.get(c, 5)
                        try:
                            clean[c] = float(val)
                        except (TypeError, ValueError):
                            clean[c] = 5.0
                    raw_scores[t.upper()] = clean
        else:
            print(f"  Failed to parse scores for batch {batch}")

    # Apply deterministic weights
    qual_scores: dict[str, float] = {}
    for t, scores in raw_scores.items():
        weighted = sum(
            scores.get(c, 5.0) * w
            for c, w in QUAL_CRITERIA_WEIGHTS.items()
        )
        qual_scores[t] = round(weighted, 3)
        print(f"  {t}: qual_score = {qual_scores[t]:.3f}  (raw: {scores})")

    return qual_scores

# COLLECT FINANCIAL DATA OF THE SUSPECT COMMPANIES
async def step_5_collect_financials(target_ticker : str , tickers_: list[str]) -> pd.DataFrame:
    """Fetch financial metrics for all tickers using yfinance.
    Returns a DataFrame with tickers as index and 10 metric columns."""
    print("═══ Step 5: Collect financial data ═══")
    import yfinance as yf
    tickers = [target_ticker] + tickers_

    metrics = list(QUANT_METRIC_WEIGHTS.keys())
    rows: dict[str, dict[str, float]] = {}
    count  = 0
    for t in tickers:
        count = count + 1
        try:
            tk = await asyncio.to_thread(yf.Ticker, t)
            info = await asyncio.to_thread(lambda: tk.info or {})
            row = {
                "market_cap":       info.get("marketCap", np.nan),
                "revenue":          info.get("totalRevenue", np.nan),
                "ebitda":           info.get("ebitda", np.nan),
                "gross_margin":     info.get("grossMargins", np.nan),
                "operating_margin": info.get("operatingMargins", np.nan),
                "profit_margin":    info.get("profitMargins", np.nan),
                "revenue_growth":   info.get("revenueGrowth", np.nan),
                "roe":              info.get("returnOnEquity", np.nan),
                "debt_to_equity":   info.get("debtToEquity", np.nan),
                "beta":             info.get("beta", np.nan),
            }
            rows[t] = row
            print(f"  {t}: OK")
        except Exception as e:
            print(f"  {t}: yfinance error — {e}")
        if (count  % 5 == 0):
          await asyncio.sleep(7)

    df = pd.DataFrame.from_dict(rows, orient="index", columns=metrics)
    # Convert to numeric, coercing errors
    df = df.apply(pd.to_numeric, errors="coerce")
    return df

# QUANTITAVE SCORING TO GET THE BEST COMPETITOR
# --- Metric categories for competitive threat logic ---
# Scale metrics: absolute size = threat (bigger = more dangerous)
SCALE_METRICS = {'market_cap', 'revenue', 'ebitda'}

# Margin metrics: sustainability of competition (higher = can fight longer)
MARGIN_METRICS = {'gross_margin', 'operating_margin', 'profit_margin', 'roe'}

# Stability metrics: financial resilience (lower debt = more durable; moderate beta = stable)
# debt_to_equity: lower is better for threat (can sustain losses)
# beta: moderate is ideal (not too volatile, not too passive)
STABILITY_METRICS = {'debt_to_equity', 'beta'}

# Growth metric: trajectory of threat
GROWTH_METRICS = {'revenue_growth'}

def step_6_quantitative_scoring(target_ticker: str,
                                 df: pd.DataFrame) -> dict[str, float]:
    """Compute quantitative competitive threat scores for each peer vs the target.
    Higher score = stronger competitive threat to the target company."""
    print("═══ Step 6: Quantitative competitive threat scoring ═══")

    if target_ticker not in df.index:
        print(f"  Target {target_ticker} not in financial data!")
        return {}

    df_work = df.copy()

    # Fill NaN with column medians
    for col in df_work.columns:
        median_val = df_work[col].median()
        df_work[col] = df_work[col].fillna(median_val if not np.isnan(median_val) else 0)

    # 1. Log-transform large-magnitude columns
    for col in ['market_cap', 'revenue', 'ebitda']:
        if col in df_work.columns:
            df_work[col] = np.log1p(df_work[col].clip(lower=0))

    # 2. Normalize to 0-1
    scaler = MinMaxScaler()
    metric_cols = list(QUANT_METRIC_WEIGHTS.keys())

    for mc in metric_cols:
        if mc not in df_work.columns:
            df_work[mc] = 0.0

    df_scaled = pd.DataFrame(
        scaler.fit_transform(df_work[metric_cols]),
        index=df_work.index,
        columns=metric_cols,
    )

    # 3. Competitive threat scoring per peer
    target_row = df_scaled.loc[target_ticker]
    peers = [t for t in df_scaled.index if t != target_ticker]

    quant_scores: dict[str, float] = {}

    for peer in peers:
        peer_row = df_scaled.loc[peer]
        weighted_threat = 0.0

        for metric, weight in QUANT_METRIC_WEIGHTS.items():

            if metric in SCALE_METRICS:
                threat = peer_row[metric]

            elif metric in MARGIN_METRICS:
                # --- MARGIN SUSTAINABILITY ---
                # Higher margins = can sustain price wars, R&D spend
                threat = peer_row[metric]

            elif metric in GROWTH_METRICS:
                # --- GROWTH TRAJECTORY ---
                # Faster growth = rising competitive threat
                threat = peer_row[metric]

            elif metric == 'debt_to_equity':
                # --- FINANCIAL LEVERAGE ---
                # Lower debt = more durable competitor (can sustain losses)
                # Invert: lower debt = higher threat
                threat = 1.0 - peer_row[metric]

            elif metric == 'beta':
                # --- MARKET SENSITIVITY ---
                # Moderate beta (around 0.5-0.7 scaled) = stable, predictable competitor
                # Too high = volatile, unpredictable; too low = passive
                # Use inverted distance from ideal moderate beta (0.6 scaled)
                ideal_beta = 0.6
                threat = 1.0 - abs(peer_row[metric] - ideal_beta)

            else:
                # Fallback
                threat = peer_row[metric]

            weighted_threat += threat * weight

        quant_scores[peer] = round(weighted_threat, 4)
        print(f"  {peer}: quant_threat = {quant_scores[peer]:.4f}")

    return quant_scores

# COMPUTE FINAL SCORES
def compute_final_scores(qual_scores: dict[str, float],
                         quant_scores: dict[str, float],
                         ) -> list[dict]:
    """Combine qualitative (0-10) and quantitative (0-1) scores into a
    final ranking.  final_score = 0.4 × (qual/10) + 0.6 × quant."""
    all_tickers = set(qual_scores.keys()) | set(quant_scores.keys())
    results = []
    for t in all_tickers:
        qs = qual_scores.get(t, 5.0)       # default 5/10 if not scored
        qt = quant_scores.get(t, 0.5)       # default 0.5 if not scored
        final = QUAL_WEIGHT * (qs / 10.0) + QUANT_WEIGHT * qt
        results.append({
            "ticker": t,
            "qual_score": round(qs, 3),
            "quant_score": round(qt, 4),
            "final_score": round(final, 4),
        })
    results.sort(key=lambda x: x['final_score'], reverse=True)
    return results

# MAIN FUNCTION
async def get_best_peers(target_ticker : str) -> str:
    ner_text = await fetch_text(target_ticker)
    ner_output = await stage_ner_gemini(ner_text)
    sec_peers = await stage_llm_resolution(target_ticker , ner_output)

    competitor_attrs , target_core_attrs = await step_2a_target_attributes(target_ticker)
    indirect_peers_ = await step_2b_discover_suspects(target_ticker , competitor_attrs , target_core_attrs , sec_peers)
    indirect_peers = json.loads(indirect_peers_)

    final_peers_ = merge_peers(target_ticker , sec_peers , indirect_peers)
    final_peers = await validate_competitor(target_ticker , final_peers_)

    peer_attrs_dict = await get_peer_attrs_dict(final_peers)
    qual_scores = await step_4_qualitative_scoring(target_ticker , target_core_attrs , peer_attrs_dict)
    df = await step_5_collect_financials(target_ticker , final_peers)
    quant_scores = step_6_quantitative_scoring(target_ticker , df)
    results_dict = compute_final_scores(qual_scores , quant_scores)
    best_competitor = results_dict[0].get("ticker")
    return best_competitor
