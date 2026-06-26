"""
Industrial-grade market intelligence news tool.
Sources: SEC 8-K filings, yfinance IR RSS, yfinance analyst up/downgrades, Google News RSS.
Outputs an Investment Signal Brief with thesis-specific + overall news, sentiment
divergence, confidence, momentum, risk flags, and credibility scoring.
"""

import asyncio
import re
import uuid
import urllib.parse
from datetime import datetime, timezone, date
from difflib import SequenceMatcher
from html import unescape

import httpx
import feedparser
import yfinance as yf
import torch
from bs4 import BeautifulSoup
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# ----------------------------------------------------------------------------- #
# Config
# ----------------------------------------------------------------------------- #
SEC_USER_AGENT = "market-intel-tool contact@example.com"   # SEC requires a UA
YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
GNEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

# Define your investment thesis here: variable name -> semantic search anchor.
THESIS = {
    "Revenue / demand":       "revenue growth demand orders sales bookings backlog",
    "Margins / profitability": "gross margin operating margin profitability pricing cost",
    "Regulatory / legal risk": "regulator antitrust lawsuit investigation export ban sanctions",
    "Competitive position":    "competition market share rivals competitor pricing pressure",
    "Capital / guidance":      "guidance outlook forecast capital expenditure buyback dividend",
}

# ----------------------------------------------------------------------------- #
# Models (loaded once)
# ----------------------------------------------------------------------------- #
_FIN_TOK = AutoTokenizer.from_pretrained("ProsusAI/finbert")
_FIN = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert").eval()
_FIN_LBL = _FIN.config.id2label
_EMBED = SentenceTransformer("all-MiniLM-L6-v2")
_DIM = 384

# ----------------------------------------------------------------------------- #
# Text utilities
# ----------------------------------------------------------------------------- #
def clean_summary(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    txt = re.sub(r"<[^>]+>", " ", text)
    txt = unescape(txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:limit].rstrip() + "…") if len(txt) > limit else txt


def chunk_text(text: str, max_tokens: int = 450) -> list[str]:
    sents = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur, n = [], [], 0
    for s in sents:
        tok = len(_FIN_TOK.encode(s, add_special_tokens=False))
        if n + tok > max_tokens and cur:
            chunks.append(" ".join(cur)); cur, n = [], 0
        cur.append(s); n += tok
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _recency_days(published) -> int | None:
    if not published:
        return None
    try:
        parsed = feedparser._parse_date(str(published))
        if not parsed:
            return None
        dt = datetime(*parsed[:6], tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


# ----------------------------------------------------------------------------- #
# Sentiment (FinBERT)
# ----------------------------------------------------------------------------- #
def finbert_score(texts: list[str]) -> list[dict]:
    if not texts:
        return []
    with torch.no_grad():
        enc = _FIN_TOK(texts, return_tensors="pt", padding=True,
                       truncation=True, max_length=512)
        probs = torch.softmax(_FIN(**enc).logits, dim=-1)
    out = []
    for row in probs:
        s = {_FIN_LBL[i].lower(): float(row[i]) for i in range(len(row))}
        net = round(s.get("positive", 0) - s.get("negative", 0), 3)
        out.append({"score": net, "confidence": round(max(s.values()), 3)})
    return out


def _label(score: float) -> str:
    if score > 0.15:
        return "Bullish"
    if score < -0.15:
        return "Bearish"
    return "Neutral"


# ----------------------------------------------------------------------------- #
# Classification: MATERIAL / CONTEXTUAL / NOISE
# ----------------------------------------------------------------------------- #
MATERIAL_KW = {
    "earnings": {"earnings", "revenue", "results", "eps", "profit", "loss", "beats", "misses"},
    "guidance": {"guidance", "forecast", "outlook", "raises", "cuts", "lowers"},
    "leadership": {"ceo", "cfo", "resign", "appoint", "steps down", "executive"},
    "legal": {"lawsuit", "probe", "antitrust", "regulator", "investigation", "settlement", "fine"},
    "m&a": {"acquire", "acquisition", "merger", "buyout", "stake", "takeover"},
    "credit": {"downgrade", "default", "liquidity", "debt", "bankruptcy", "rating cut"},
}
CONTEXTUAL_KW = {"launch", "unveil", "partnership", "collaborat", "product",
                 "industry", "market", "competitor", "rival", "trend", "expansion"}
NOISE_KW = {"award", "ranking", "best stocks", "top 10", "opinion", "why you should",
            "should you buy", "motley", "here's how", "5 stocks", "3 stocks"}


def classify_item(item: dict) -> str:
    t = (item["title"] + " " + item.get("summary", "")).lower()
    for cat in MATERIAL_KW.values():
        if any(k in t for k in cat):
            return "MATERIAL"
    if any(k in t for k in NOISE_KW):
        return "NOISE"
    if any(k in t for k in CONTEXTUAL_KW):
        return "CONTEXTUAL"
    return "CONTEXTUAL"


def _weight(cat: str) -> float:
    return {"MATERIAL": 1.0, "CONTEXTUAL": 0.5, "NOISE": 0.1}[cat]


# ----------------------------------------------------------------------------- #
# Fetchers
# ----------------------------------------------------------------------------- #
async def fetch_og_description(client: httpx.AsyncClient, url: str | None) -> str:
    """Fetch og:description or meta description from article URL. Reads only first 8KB."""
    if not url:
        return ""
    try:
        # Stream only — read first 8KB, enough to get <head> content
        async with client.stream("GET", url, timeout=8, 
                                  headers={"Range": "bytes=0-8192"}) as r:
            chunk = await r.aread()
        html = chunk.decode("utf-8", errors="ignore")
        
        # Try og:description first (richer), fall back to meta description
        for pattern in [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{20,})["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{20,})["\']',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
                return text[:350] + "…" if len(text) > 350 else text
    except Exception:
        pass
    return ""

async def enrich_with_descriptions(items: list[dict]) -> list[dict]:
    """Batch-fetch descriptions only for items missing a meaningful summary."""
    
    needs_enrichment = [
        i for i, n in enumerate(items) 
        if len(n.get("summary", "")) < 80  # summary too short to be useful
    ]
    
    if not needs_enrichment:
        return items
    
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as cl:
        tasks = [
            fetch_og_description(cl, items[i]["link"]) 
            for i in needs_enrichment
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for idx, result in zip(needs_enrichment, results):
        if isinstance(result, str) and result:
            items[idx]["summary"] = result
            items[idx]["summary_source"] = "og:description"  # track provenance
    
    return items

async def fetch_ir(ticker: str) -> list[dict]:
    """Company / IR voice: yfinance news + Yahoo RSS. Tier T2."""
    def _pull():
        try:
            return yf.Ticker(ticker).news or []
        except Exception:
            return []
    items = await asyncio.to_thread(_pull)

    out = []
    for n in items:
        c = n.get("content", n)
        title = c.get("title") or n.get("title", "")
        if not title:
            continue
        out.append({
            "title": title,
            "summary": c.get("summary", "") or c.get("description", ""),
            "link": (c.get("canonicalUrl") or {}).get("url") or n.get("link"),
            "published": c.get("pubDate") or n.get("providerPublishTime"),
            "source": (c.get("provider") or {}).get("displayName", "Yahoo Finance"),
            "tier": "T2", "stream": "IR",
        })

    async with httpx.AsyncClient(timeout=15) as cl:
        try:
            r = await cl.get(YAHOO_RSS.format(ticker=ticker))
            for e in feedparser.parse(r.text).entries:
                out.append({
                    "title": e.title, "summary": e.get("summary", ""),
                    "link": e.link, "published": e.get("published"),
                    "source": "Yahoo RSS", "tier": "T2", "stream": "IR",
                })
        except Exception:
            pass
    out = await enrich_with_descriptions(out)
    return out


async def fetch_public(company: str, limit: int = 30) -> list[dict]:
    """Public / media voice: Google News RSS. Tier T3."""
    q = urllib.parse.quote(f'"{company}"')
    out = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as cl:
        try:
            r = await cl.get(GNEWS.format(q=q))
            for e in feedparser.parse(r.text).entries[:limit]:
                out.append({
                    "title": e.title, "summary": e.get("summary", ""),
                    "link": e.link, "published": e.get("published"),
                    "source": (e.get("source", {}) or {}).get("title", "Media"),
                    "tier": "T3", "stream": "PUBLIC",
                })
        except Exception:
            pass
    return out


async def fetch_analyst(ticker: str) -> list[dict]:
    """Analyst upgrades / downgrades via yfinance. Tier T2."""
    def _pull():
        try:
            df = yf.Ticker(ticker).upgrades_downgrades
            if df is None or df.empty:
                return []
            df = df.reset_index().head(8)
            rows = []
            for _, r in df.iterrows():
                firm = r.get("Firm", "Analyst")
                frm = r.get("FromGrade", "") or ""
                to = r.get("ToGrade", "") or ""
                action = (r.get("Action", "") or "").lower()
                gd = r.get("GradeDate")
                rows.append({"firm": firm, "from": frm, "to": to,
                             "action": action, "date": str(gd) if gd is not None else None})
            return rows
        except Exception:
            return []
    raw = await asyncio.to_thread(_pull)

    out = []
    for r in raw:
        verb = ("upgraded" if "up" in r["action"] else
                "downgraded" if "down" in r["action"] else "reiterated")
        title = f"{r['firm']} {verb} {ticker}" + (f" to {r['to']}" if r["to"] else "")
        summary = (f"{r['firm']} moved its rating from "
                   f"{r['from'] or 'n/a'} to {r['to'] or 'n/a'}.")
        out.append({
            "title": title, "summary": summary, "link": None,
            "published": r["date"], "source": r["firm"],
            "tier": "T2", "stream": "ANALYST",
            "_analyst_dir": 1 if "up" in r["action"] else -1 if "down" in r["action"] else 0,
        })
    return out


async def fetch_8k(ticker: str) -> list[dict]:
    """SEC 8-K material-event filings via EDGAR. Tier T1 (ground truth)."""
    ITEM_MEANING = {
        "1.01": "Material definitive agreement (M&A / contract)",
        "1.03": "Bankruptcy or receivership",
        "2.02": "Results of operations (earnings)",
        "2.03": "Material financial obligation (debt)",
        "4.02": "Non-reliance on prior financials (restatement)",
        "5.02": "Departure/appointment of directors or officers (leadership)",
        "7.01": "Regulation FD disclosure",
        "8.01": "Other material event",
    }

    def _pull():
        headers = {"User-Agent": SEC_USER_AGENT}
        try:
            t = yf.Ticker(ticker)
            cik = None
            info = getattr(t, "info", {}) or {}
            # resolve CIK via SEC ticker map
            with httpx.Client(timeout=20, headers=headers) as c:
                m = c.get("https://www.sec.gov/files/company_tickers.json").json()
                for v in m.values():
                    if v["ticker"].upper() == ticker.upper():
                        cik = str(v["cik_str"]).zfill(10)
                        break
                if not cik:
                    return []
                subs = c.get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
                rec = subs["filings"]["recent"]
                results = []
                for form, acc, doc, dt, items in zip(
                        rec["form"], rec["accessionNumber"], rec["primaryDocument"],
                        rec["filingDate"], rec.get("items", [""] * len(rec["form"]))):
                    if form != "8-K":
                        continue
                    codes = [i.strip() for i in (items or "").split(",") if i.strip()]
                    meanings = [ITEM_MEANING.get(c, f"Item {c}") for c in codes] or ["8-K filing"]
                    results.append({"acc": acc, "date": dt, "codes": codes,
                                    "meanings": meanings})
                    if len(results) >= 5:
                        break
                return results
        except Exception:
            return []
    filings = await asyncio.to_thread(_pull)

    out = []
    for f in filings:
        desc = "; ".join(f["meanings"])
        out.append({
            "title": f"SEC 8-K filed {f['date']}: {f['meanings'][0]}",
            "summary": f"Items: {desc}.",
            "link": None, "published": f["date"], "source": "SEC EDGAR",
            "tier": "T1", "stream": "SEC",
            "_codes": f["codes"],
        })
    return out


# ----------------------------------------------------------------------------- #
# Enrichment + dedupe
# ----------------------------------------------------------------------------- #
async def enrich(items: list[dict]) -> list[dict]:
    if not items:
        return items
    scored = await asyncio.to_thread(
        finbert_score, [i["title"] + ". " + clean_summary(i.get("summary", ""), 300)
                        for i in items])
    for it, s in zip(items, scored):
        # analyst direction overrides headline tone where known
        adir = it.get("_analyst_dir")
        it["sentiment_score"] = (0.6 if adir == 1 else -0.6 if adir == -1 else s["score"])
        it["sentiment"] = _label(it["sentiment_score"])
        it["confidence"] = s["confidence"]
        it["category"] = "MATERIAL" if it["stream"] == "SEC" else classify_item(it)
        it["weight"] = _weight(it["category"]) * (1.3 if it["tier"] == "T1"
                                                  else 1.15 if it["tier"] == "T2" else 1.0)
        it["age_days"] = _recency_days(it.get("published"))
    return items


def dedupe(items: list[dict], thresh: float = 0.82) -> tuple[list[dict], int]:
    kept, removed = [], 0
    for it in items:
        if any(SequenceMatcher(None, it["title"].lower(), k["title"].lower()).ratio() > thresh
               for k in kept):
            removed += 1
            continue
        kept.append(it)
    return kept, removed


# ----------------------------------------------------------------------------- #
# Qdrant index + thesis engine
# ----------------------------------------------------------------------------- #
class NewsIndex:
    def __init__(self, name: str = "news"):
        self.client = QdrantClient(":memory:")
        self.coll = name
        self.client.recreate_collection(
            self.coll, vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE))

    def add(self, items: list[dict]):
        if not items:
            return
        vecs = _EMBED.encode([i["title"] + ". " + clean_summary(i.get("summary", ""), 300)
                              for i in items], normalize_embeddings=True)
        self.client.upsert(self.coll, points=[
            PointStruct(id=str(uuid.uuid4()), vector=v.tolist(), payload=it)
            for v, it in zip(vecs, items)])

    def query(self, anchor: str, k: int = 5, threshold: float = 0.40):
        q = _EMBED.encode([anchor], normalize_embeddings=True)[0].tolist()
        hits = self.client.query_points(
            collection_name=self.coll,
            query=q,       
            limit=k
        )
        return [(h.payload, h.score) for h in hits.points if h.score >= threshold]


def evaluate_thesis(index: NewsIndex, company: str) -> dict:
    touched, untouched = [], []
    for var, anchor in THESIS.items():
        hits = index.query(f"{company} {anchor}", k=5)
        if not hits:
            untouched.append(var)
            continue
        items = [h[0] for h in hits]
        avg = round(sum(i["sentiment_score"] for i in items) / len(items), 3)
        conf = round(sum(i["confidence"] for i in items) / len(items), 3)
        top = items[0]
        sources = {i["source"] for i in items}
        touched.append({
            "variable": var,
            "direction": ("POSITIVE" if avg > 0.1 else "NEGATIVE" if avg < -0.1 else "MIXED"),
            "score": avg, "confidence": conf,
            "headline": top["title"],
            "description": clean_summary(top.get("summary", "")),
            "source": top["source"], "tier": top.get("tier", "T3"),
            "verified": len(sources) >= 2,
        })
    return {"touched": touched, "untouched": untouched,
            "monitored": len(THESIS), "touched_count": len(touched)}


# ----------------------------------------------------------------------------- #
# Aggregations
# ----------------------------------------------------------------------------- #
def aggregate(items: list[dict]) -> dict:
    if not items:
        return {"label": "Neutral", "score": 0.0, "count": 0,
                "confidence": 0.0, "material_count": 0}
    w = sum(i["weight"] for i in items) or 1
    avg = round(sum(i["sentiment_score"] * i["weight"] for i in items) / w, 3)
    return {
        "label": _label(avg), "score": avg, "count": len(items),
        "confidence": round(sum(i["confidence"] for i in items) / len(items), 3),
        "material_count": sum(1 for i in items if i["category"] == "MATERIAL"),
    }


def detect_material(items: list[dict]) -> dict:
    mats = [i for i in items if i["category"] == "MATERIAL"]
    if not mats:
        return {"detected": False, "source": "-", "tier": "-", "explanation": "None this cycle"}
    rank = {"T1": 0, "T2": 1, "T3": 2, "T4": 3}
    top = sorted(mats, key=lambda x: (rank.get(x["tier"], 9), x.get("age_days") or 999))[0]
    return {"detected": True, "source": top["source"], "tier": top["tier"],
            "explanation": top["title"]}


def momentum(items: list[dict]) -> dict:
    rec = [i["sentiment_score"] for i in items if (i.get("age_days") or 99) <= 7]
    pri = [i["sentiment_score"] for i in items if 7 < (i.get("age_days") or 99) <= 14]
    r = sum(rec) / len(rec) if rec else 0
    p = sum(pri) / len(pri) if pri else 0
    d = round(r - p, 3)
    return {"trend": "Improving" if d > 0.1 else "Deteriorating" if d < -0.1 else "Stable",
            "delta": d, "inflection": "Sentiment sign flip detected" if r * p < 0 else None}


def risk_flags(items: list[dict]) -> list[str]:
    flags = set()
    for i in items:
        t = (i["title"] + " " + i.get("summary", "")).lower()
        if any(k in t for k in MATERIAL_KW["legal"]):      flags.add("Litigation / regulatory")
        if any(k in t for k in MATERIAL_KW["leadership"]): flags.add("Leadership change")
        if any(k in t for k in MATERIAL_KW["credit"]):     flags.add("Credit / liquidity")
        if any(k in t for k in {"tariff", "recession", "rate hike", "inflation", "macro"}):
            flags.add("Macro exposure")
    return sorted(flags) or ["None detected"]


def credibility(items: list[dict]) -> dict:
    tiers = {}
    for i in items:
        tiers[i["tier"]] = tiers.get(i["tier"], 0) + 1
    t1, t2 = tiers.get("T1", 0), tiers.get("T2", 0)
    if len(items) < 3:
        q = "Insufficient"
    elif t1 >= 1 and t2 >= 1:
        q = "High"
    elif (t1 + t2) >= 1:
        q = "Medium"
    else:
        q = "Low"
    return {"quality": q, "breakdown": ", ".join(f"{k}: {v}" for k, v in sorted(tiers.items()))}


# ----------------------------------------------------------------------------- #
# Human-readable interpretation + rendering
# ----------------------------------------------------------------------------- #
def interpret_item(i: dict) -> str:
    direction = {"Bullish": "a positive signal", "Bearish": "a concern",
                 "Neutral": "a neutral development"}[i["sentiment"]]
    weight = {"MATERIAL": "Material — can directly move the stock",
              "CONTEXTUAL": "Context — unlikely to move the stock alone",
              "NOISE": "Low importance"}[i["category"]]
    trust = {"T1": "official/primary source (high trust)",
             "T2": "credible outlet (good trust)",
             "T3": "general media (verify before acting)",
             "T4": "social chatter (low trust)"}.get(i["tier"], "")
    return f"{weight}; reads as {direction}, from a {trust}."


def situation_summary(d: dict) -> str:
    s, mat, m = d["sentiment"], d["material"], d["momentum"]
    parts = []
    if mat["detected"]:
        parts.append(f"Material event detected: {mat['explanation']} "
                     f"({mat['source']}, {mat['tier']}).")
    else:
        parts.append("No material market-moving event detected this cycle.")
    ir_l, pub_l = s["institutional_ir"]["label"], s["public"]["label"]
    if s["divergence"]["diverging"]:
        parts.append(f"Company/IR messaging looks {ir_l.lower()} while public sentiment is "
                     f"{pub_l.lower()} — a notable divergence ({s['divergence']['note']}), "
                     f"often flagging an overlooked opportunity or unresolved risk.")
    else:
        parts.append(f"Company messaging ({ir_l.lower()}) and public sentiment "
                     f"({pub_l.lower()}) are broadly aligned.")
    parts.append(f"7-day news momentum is {m['trend'].lower()}. "
                 f"Overall: {d['bottom_line'].lower()}.")
    return " ".join(parts)


def _bullets(items: list[dict], n: int = 6) -> str:
    order = {"MATERIAL": 0, "CONTEXTUAL": 1, "NOISE": 2}
    ranked = sorted([i for i in items if i["category"] != "NOISE"],
                    key=lambda x: (order[x["category"]], x.get("age_days") or 999))[:n]
    if not ranked:
        return "     (no significant items)"
    icon = {"Bullish": "▲", "Bearish": "▼", "Neutral": "■"}
    out = []
    for i in ranked:
        age = f"{i['age_days']}d ago" if i.get("age_days") is not None else "recent"
        out.append(f"  {icon[i['sentiment']]} {i['title']}")
        out.append(f"      {i['source']} ({i['tier']}) · {age} · "
                   f"sentiment {i['sentiment']} · confidence {i['confidence']}")
        desc = clean_summary(i.get("summary", ""))
        if desc:
            out.append(f"      What happened: {desc}")
        out.append("")
    return "\n".join(out).rstrip()


def render_brief(d: dict) -> str:
    s, th, m = d["sentiment"], d["thesis"], d["momentum"]
    mat, cred = d["material"], d["credibility"]
    div = s["divergence"]

    thesis_lines = []
    for t in th["touched"]:
        mk = {"POSITIVE": "[+]", "NEGATIVE": "[-]", "MIXED": "[~]"}[t["direction"]]
        ver = "Confirmed (2+ sources)" if t["verified"] else "Unverified (single source)"
        thesis_lines.append(f"  {mk} {t['variable']}: {t['direction']} "
                            f"(score {t['score']}, conf {t['confidence']})")
        thesis_lines.append(f"      \"{t['headline']}\"")
        thesis_lines.append(f"      {t['source']} ({t['tier']}) · {ver}")
        thesis_lines.append("")
    for u in th["untouched"]:
        thesis_lines.append(f"  ( ) {u}: No news this cycle")
    thesis_block = "\n".join(thesis_lines).rstrip()

    net = sum(t["score"] for t in th["touched"])
    thesis_dir = "Strengthens" if net > 0.2 else "Weakens" if net < -0.2 else "Neutral"

    return f"""
================================================================
  INVESTMENT SIGNAL BRIEF — {d['ticker']} — {date.today()}
  ({d['company']})
================================================================

SITUATION SUMMARY
  {situation_summary(d)}

THESIS IMPACT
  -> Material event?  {"YES" if mat['detected'] else "NO"}  [{mat['source']} {mat['tier']}]
     {mat['explanation']}
  -> Thesis change?   {thesis_dir}
  -> Variables: {th['monitored']} monitored / {th['touched_count']} touched

THESIS-SPECIFIC NEWS
{thesis_block}

OVERALL NEWS — WHAT THE COMPANY SAYS (IR / Analysts / SEC)
{_bullets(d['_company'])}

OVERALL NEWS — WHAT PEOPLE BELIEVE (Media)
{_bullets(d['_public'])}

SENTIMENT DASHBOARD
  -> Institutional (IR/SEC/Analyst):  {s['institutional_ir']['label']}  "
        f"(score {s['institutional_ir']['score']}, conf {s['institutional_ir']['confidence']})
  -> Public (Media):                  {s['public']['label']}  "
        f"(score {s['public']['score']}, {s['public']['count']} items)
  -> Overall:                         {s['overall']['label']}  (score {s['overall']['score']})
  -> Divergence:                      {"!! " + div['note'] if div['diverging'] else div['note']}

MOMENTUM
  -> 7-day trend:    {m['trend']}  (delta {m['delta']})
  -> Inflection:     {m['inflection'] or "none"}

RISK FLAGS
  -> {", ".join(d['risks'])}

CREDIBILITY
  -> Signal quality: {cred['quality']}
  -> Source breakdown: [{cred['breakdown']}]
  -> Noise filtered:  {d['noise_count']} duplicate/low-value items removed

BOTTOM LINE
  -> {d['bottom_line']}
================================================================
"""


# ----------------------------------------------------------------------------- #
# Main pipeline
# ----------------------------------------------------------------------------- #
async def analyze(ticker: str, company: str) -> dict:
    ir, public, analyst, sec = await asyncio.gather(
        fetch_ir(ticker), fetch_public(company),
        fetch_analyst(ticker), fetch_8k(ticker),
        return_exceptions=True)
    ir = ir if isinstance(ir, list) else []
    public = public if isinstance(public, list) else []
    analyst = analyst if isinstance(analyst, list) else []
    sec = sec if isinstance(sec, list) else []

    company_stream = sec + analyst + ir            # company/official voice
    company_stream, dup1 = dedupe(company_stream)
    public, dup2 = dedupe(public)

    company_stream, public = await asyncio.gather(
        enrich(company_stream), enrich(public))

    index = NewsIndex()
    index.add(company_stream); index.add(public)
    thesis = evaluate_thesis(index, company)

    all_items = company_stream + public
    comp_sent = aggregate(company_stream)
    pub_sent = aggregate(public)
    overall = aggregate(all_items)
    divergence = round(comp_sent["score"] - pub_sent["score"], 3)
    noise_count = (dup1 + dup2 + sum(1 for i in all_items if i["category"] == "NOISE"))

    net = sum(t["score"] for t in thesis["touched"])
    bottom_line = ("News flow supports the investment case"
                   if net > 0.2 and overall["score"] > 0 else
                   "News flow challenges the investment case"
                   if net < -0.2 or overall["score"] < -0.15 else
                   "News flow is neutral on the investment case")

    d = {
        "ticker": ticker, "company": company,
        "_company": company_stream, "_public": public,
        "thesis": thesis,
        "material": detect_material(all_items),
        "sentiment": {
            "institutional_ir": comp_sent, "public": pub_sent, "overall": overall,
            "divergence": {"value": divergence, "diverging": abs(divergence) > 0.3,
                           "note": "IR more bullish than public" if divergence > 0.3
                                   else "Public more bullish than IR" if divergence < -0.3
                                   else "IR and public broadly aligned"}},
        "momentum": momentum(all_items),
        "risks": risk_flags(all_items),
        "credibility": credibility(all_items),
        "noise_count": noise_count,
        "bottom_line": bottom_line,
    }
    return d

import os 
from edgar import Company , set_identity

set_identity(os.environ.get("EDGAR_IDENTITY"))

async def main(ticker: str, peers: list[str]) -> dict:
    all_tickers = [ticker] + peers

    async def analyze_one(t: str) -> dict:
        company = Company(t).name
        d = await analyze(t, company)
        return render_brief(d)

    results = await asyncio.gather(
        *[analyze_one(t) for t in all_tickers],
        return_exceptions=True
    )

    return {
        t: r if not isinstance(r, Exception) else {"error": str(r)}
        for t, r in zip(all_tickers, results)
    }

if __name__ == "__main__":
    asyncio.run(main("NVDA"))