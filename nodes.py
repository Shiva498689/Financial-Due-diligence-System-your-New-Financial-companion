import asyncio
import os
from langgraph.graph import START, END, StateGraph
from typing import TypedDict, Optional, List, Any, Dict, NotRequired
from quant_engine_metrics import EdgarFinancialExtractor
from analysis_agent import calculate_all_scores
from quant_web import run_pipeline
import json
from consumer_analysis import analysis_genrator
from miagent_mcp import get_market_metrics
from google.genai.types import GenerateContentConfig
from google import genai
from ingestion_agent import run_ingestion_pipeline
# Read API key from environment; fall back to the hardcoded dev key
GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AQ.Ab8RN6KVewqbkCQ_dyxNcUGGllh9J4XkmRk3R5AMN1TEuLQgeg",
)
GEMINI_MODEL = "gemini-3.5-flash-lite"

client = genai.Client(api_key=GEMINI_API_KEY)


class AgentState(TypedDict):
    gemini_api_key: str
    ticker: str

    # ------------ Income Statement ------------
    revenue_latest: NotRequired[Optional[float]]
    revenue_previous: NotRequired[Optional[float]]
    cogs_latest: NotRequired[Optional[float]]
    cogs_previous: NotRequired[Optional[float]]
    gross_profit_latest: NotRequired[Optional[float]]
    gross_profit_previous: NotRequired[Optional[float]]
    sga_expenses_latest: NotRequired[Optional[float]]
    sga_expenses_previous: NotRequired[Optional[float]]
    depreciation_amortization_latest: NotRequired[Optional[float]]
    depreciation_amortization_previous: NotRequired[Optional[float]]
    net_income_latest: NotRequired[Optional[float]]
    net_income_previous: NotRequired[Optional[float]]
    net_income_continuing_ops_latest: NotRequired[Optional[float]]
    net_income_continuing_ops_previous: NotRequired[Optional[float]]
    operating_income_latest: NotRequired[Optional[float]]
    operating_income_previous: NotRequired[Optional[float]]
    interest_expense_latest: NotRequired[Optional[float]]
    interest_expense_previous: NotRequired[Optional[float]]
    income_tax_latest: NotRequired[Optional[float]]
    income_tax_previous: NotRequired[Optional[float]]

    # ------------ Cash Flow ------------
    operating_cash_flow_latest: NotRequired[Optional[float]]
    operating_cash_flow_previous: NotRequired[Optional[float]]
    capex_latest: NotRequired[Optional[float]]
    capex_previous: NotRequired[Optional[float]]

    # ------------ Balance Sheet ------------
    current_assets_latest: NotRequired[Optional[float]]
    current_assets_previous: NotRequired[Optional[float]]
    current_liabilities_latest: NotRequired[Optional[float]]
    current_liabilities_previous: NotRequired[Optional[float]]
    cash_and_equivalents_latest: NotRequired[Optional[float]]
    cash_and_equivalents_previous: NotRequired[Optional[float]]
    receivables_latest: NotRequired[Optional[float]]
    receivables_previous: NotRequired[Optional[float]]
    inventory_latest: NotRequired[Optional[float]]
    inventory_previous: NotRequired[Optional[float]]
    gross_ppe_latest: NotRequired[Optional[float]]
    gross_ppe_previous: NotRequired[Optional[float]]
    total_assets_latest: NotRequired[Optional[float]]
    total_assets_previous: NotRequired[Optional[float]]
    total_liabilities_latest: NotRequired[Optional[float]]
    total_liabilities_previous: NotRequired[Optional[float]]
    long_term_debt_latest: NotRequired[Optional[float]]
    long_term_debt_previous: NotRequired[Optional[float]]
    short_term_debt_latest: NotRequired[Optional[float]]
    short_term_debt_previous: NotRequired[Optional[float]]
    shareholders_equity_latest: NotRequired[Optional[float]]
    shareholders_equity_previous: NotRequired[Optional[float]]
    retained_earnings_latest: NotRequired[Optional[float]]
    retained_earnings_previous: NotRequired[Optional[float]]
    working_capital_latest: NotRequired[Optional[float]]
    working_capital_previous: NotRequired[Optional[float]]
    common_shares_outstanding_latest: NotRequired[Optional[float]]
    common_shares_outstanding_previous: NotRequired[Optional[float]]

    # ------------ Score outputs ------------
    piotroski_f_score: NotRequired[Optional[int]]
    beneish_m_score: NotRequired[Optional[float]]
    ohlson_o_score_probability: NotRequired[Optional[float]]
    merton_distance_to_default: NotRequired[Optional[float]]
    deterministic_dcf_value: NotRequired[Optional[float]]
    monte_carlo_p10_floor: NotRequired[Optional[float]]
    monte_carlo_p50_median: NotRequired[Optional[float]]
    monte_carlo_p90_ceiling: NotRequired[Optional[float]]

    # ------------ MI agent outputs ------------
    current_equity_price: NotRequired[Optional[float]]
    market_capitalization: NotRequired[Optional[float]]
    historical_equity_volatility_252d: NotRequired[Optional[float]]
    risk_free_rate: NotRequired[Optional[float]]
    gnp_deflator: NotRequired[Optional[float]]
    company_description: NotRequired[Optional[str]]

    # ------------ RI agent outputs ------------
    metric_name: NotRequired[Optional[str]]
    computed_value: NotRequired[Any]
    formula_expression: NotRequired[Optional[str]]
    inputs_referenced: NotRequired[List[str]]

    # ------------ Pipeline outputs ------------
    risk_report: NotRequired[Dict[str, Any]]
    quant_analysis: NotRequired[List[Dict[Any, Any]]]
    narrative_analysis: NotRequired[List[Dict[Any, Any]]]
    markdown_report: NotRequired[str]
    docx_path: NotRequired[str]
    excel_path: NotRequired[str]


async def quant_web_node(state: AgentState) -> AgentState:
    api_key = state.get("gemini_api_key") or GEMINI_API_KEY
    audit_ledger = await run_pipeline(
        state["ticker"],
        api_key,
    )
    return {
        "quant_analysis": audit_ledger,
    }


async def narrative_analysis_node(state: AgentState) -> AgentState:
    answer = await analysis_genrator(state["ticker"])
    return {
        "narrative_analysis": answer,
    }


async def Risk_flagging_node(state: AgentState) -> AgentState:
    risk_report = {}

    # ── Piotroski F-Score ──────────────────────────────────────────────────────
    f = state.get("piotroski_f_score")
    if f is None:
        f_flag = "UNAVAILABLE"
    elif f >= 7:
        f_flag = "LOW_RISK"
    elif f >= 4:
        f_flag = "MEDIUM_RISK"
    else:
        f_flag = "HIGH_RISK"
    risk_report["piotroski"] = {
        "score": f,
        "risk": f_flag,
        "interpretation": "Higher score indicates strong financial strength and improving fundamentals",
    }

    # ── Beneish M-Score ────────────────────────────────────────────────────────
    m = state.get("beneish_m_score")
    if m is None:
        m_flag = "UNAVAILABLE"
    elif m < -2.5:
        m_flag = "LOW_RISK"
    elif m < -1.5:
        m_flag = "MEDIUM_RISK"
    else:
        m_flag = "HIGH_RISK (possible earnings manipulation)"
    risk_report["beneish"] = {
        "score": m,
        "risk": m_flag,
        "interpretation": "Detects probability of earnings manipulation",
    }

    # ── Ohlson O-Score ─────────────────────────────────────────────────────────
    o = state.get("ohlson_o_score_probability")
    if o is None:
        o_flag = "UNAVAILABLE"
    elif o < 0.3:
        o_flag = "LOW_RISK"
    elif o < 0.6:
        o_flag = "MEDIUM_RISK"
    else:
        o_flag = "HIGH_RISK (distress probability elevated)"
    risk_report["ohlson"] = {
        "score": o,
        "risk": o_flag,
        "interpretation": "Probability of financial distress",
    }

    d = state.get("merton_distance_to_default")
    if d is None:
        d_flag = "UNAVAILABLE"
    elif d > 2.5:
        d_flag = "LOW_RISK"
    elif d > 1.0:
        d_flag = "MEDIUM_RISK"
    else:
        d_flag = "HIGH_RISK (default proximity)"
    risk_report["merton"] = {
        "score": d,
        "risk": d_flag,
        "interpretation": "Distance from default boundary (structural credit risk)",
    }

    p10 = state.get("monte_carlo_p10_floor") or 0.0
    p50 = state.get("monte_carlo_p50_median") or 0.0
    p90 = state.get("monte_carlo_p90_ceiling") or 0.0
    if p50 > 0:
        upside = (p90 - p50) / p50
        downside = (p50 - p10) / p50
        if upside < 0.2 and downside < 0.2:
            dcf_flag = "LOW_RISK"
        elif upside < 0.5:
            dcf_flag = "MEDIUM_RISK"
        else:
            dcf_flag = "HIGH_RISK (valuation uncertainty high)"
    else:
        dcf_flag = "UNAVAILABLE"
    risk_report["dcf_risk"] = {
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "risk": dcf_flag,
        "interpretation": "Measures uncertainty in valuation distribution",
    }

    total = 0
    count = 0
    for k in ["piotroski", "beneish", "ohlson", "merton", "dcf_risk"]:
        r = risk_report[k]["risk"]
        if "HIGH" in r:
            total += 3
            count += 1
        elif "MEDIUM" in r:
            total += 2
            count += 1
        elif "LOW" in r:
            total += 1
            count += 1
        # UNAVAILABLE entries excluded from the average

    if count == 0:
        overall = "INSUFFICIENT DATA"
        avg_risk = 0.0
    else:
        avg_risk = total / count
        if avg_risk <= 1.4:
            overall = "HEALTHY (Low Risk Company)"
        elif avg_risk <= 2.2:
            overall = "MODERATE RISK"
        else:
            overall = "STRESSED / HIGH RISK COMPANY"

    risk_report["overall_assessment"] = {
        "average_risk_score": avg_risk,
        "final_verdict": overall,
        "components_analyzed": count,
    }
    return {"risk_report": risk_report}


async def miAgentnode(state: AgentState):
    """Fetch market metrics; gracefully handles errors from get_market_metrics."""
    try:
        
        metrics = await asyncio.to_thread(get_market_metrics, state["ticker"])
        # get_market_metrics may return {"error": "..."} on failure
        if "error" in metrics:
            print(f"[!] miAgentnode: get_market_metrics error — {metrics['error']}")
            return {
                "gnp_deflator": None,
                "current_equity_price": None,
                "market_capitalization": None,
                "historical_equity_volatility_252d": None,
                "risk_free_rate": None,
                "company_description": None,
            }
        return {
            "gnp_deflator": metrics.get("gnp_deflator"),
            "current_equity_price": metrics.get("current_equity_price"),
            "market_capitalization": metrics.get("market_capitalization"),
            "historical_equity_volatility_252d": metrics.get("historical_equity_volatility_252d"),
            "risk_free_rate": metrics.get("risk_free_rate"),
            "company_description": metrics.get("company_description"),
        }
    except Exception as e:
        print(f"[!] miAgentnode unexpected error: {e}")
        return {
            "gnp_deflator": None,
            "current_equity_price": None,
            "market_capitalization": None,
            "historical_equity_volatility_252d": None,
            "risk_free_rate": None,
            "company_description": None,
        }


async def Analysis_agent_node(state: AgentState) -> AgentState:
    a = calculate_all_scores(state)
    monte_carlo = a.get("monte_carlo_dcf") or {}
    return {
        "piotroski_f_score": a.get("piotroski_f_score"),
        "ohlson_o_score_probability": a.get("ohlson_o_score_probability"),
        "beneish_m_score": a.get("beneish_m_score"),
        "merton_distance_to_default": a.get("merton_distance_to_default"),
        "deterministic_dcf_value": monte_carlo.get("deterministic_dcf_value"),
        "monte_carlo_p10_floor": monte_carlo.get("monte_carlo_p10_floor"),
        "monte_carlo_p50_median": monte_carlo.get("monte_carlo_p50_median"),
        "monte_carlo_p90_ceiling": monte_carlo.get("monte_carlo_p90_ceiling"),
    }


from memo_agent import generate_memo_async

async def report_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return await generate_memo_async(state)


async def ingestion_node(state: AgentState) -> AgentState:
    ticker = state["ticker"]
    await run_ingestion_pipeline(ticker)
    extractor = EdgarFinancialExtractor(ticker)
    metrics = await asyncio.to_thread(extractor.extract)
    return {
        "revenue_latest": metrics.revenue_latest,
        "revenue_previous": metrics.revenue_previous,
        "cogs_latest": metrics.cogs_latest,
        "cogs_previous": metrics.cogs_previous,
        "gross_profit_latest": metrics.gross_profit_latest,
        "gross_profit_previous": metrics.gross_profit_previous,
        "sga_expenses_latest": metrics.sga_expenses_latest,
        "sga_expenses_previous": metrics.sga_expenses_previous,
        "depreciation_amortization_latest": metrics.depreciation_amortization_latest,
        "depreciation_amortization_previous": metrics.depreciation_amortization_previous,
        "net_income_latest": metrics.net_income_latest,
        "net_income_previous": metrics.net_income_previous,
        "net_income_continuing_ops_latest": metrics.net_income_continuing_ops_latest,
        "net_income_continuing_ops_previous": metrics.net_income_continuing_ops_previous,
        "operating_cash_flow_latest": metrics.operating_cash_flow_latest,
        "operating_cash_flow_previous": metrics.operating_cash_flow_previous,
        "capex_latest": metrics.capex_latest,
        "capex_previous": metrics.capex_previous,
        "current_assets_latest": metrics.current_assets_latest,
        "current_assets_previous": metrics.current_assets_previous,
        "current_liabilities_latest": metrics.current_liabilities_latest,
        "current_liabilities_previous": metrics.current_liabilities_previous,
        "cash_and_equivalents_latest": metrics.cash_and_equivalents_latest,
        "cash_and_equivalents_previous": metrics.cash_and_equivalents_previous,
        "receivables_latest": metrics.receivables_latest,
        "receivables_previous": metrics.receivables_previous,
        "gross_ppe_latest": metrics.gross_ppe_latest,
        "gross_ppe_previous": metrics.gross_ppe_previous,
        "total_assets_latest": metrics.total_assets_latest,
        "total_assets_previous": metrics.total_assets_previous,
        "total_liabilities_latest": metrics.total_liabilities_latest,
        "total_liabilities_previous": metrics.total_liabilities_previous,
        "long_term_debt_latest": metrics.long_term_debt_latest,
        "long_term_debt_previous": metrics.long_term_debt_previous,
        "short_term_debt_latest": metrics.short_term_debt_latest,
        "short_term_debt_previous": metrics.short_term_debt_previous,
    }
