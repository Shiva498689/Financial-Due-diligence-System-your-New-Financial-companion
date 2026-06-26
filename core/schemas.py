from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict

class AnnualFinancials(BaseModel):
    # Income Statement (Optional to allow graceful fallbacks)
    revenue: Optional[float] = None
    cogs: Optional[float] = None
    gross_profit: Optional[float] = None
    sga_expenses: Optional[float] = None
    depreciation_amortization: Optional[float] = None
    net_income: Optional[float] = None
    net_income_continuing_ops: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    # Balance Sheet (Optional to allow graceful fallbacks)
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    receivables: Optional[float] = None
    gross_ppe: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    long_term_debt: Optional[float] = None
    short_term_debt: Optional[float] = None
    shareholders_equity: Optional[float] = None
    common_shares_outstanding: Optional[float] = None

class MarketIntelPayload(BaseModel):
    current_equity_price: float
    market_capitalization: float
    historical_equity_volatility_252d: float
    risk_free_rate: float
    gnp_deflator: float

class AuditEntry(BaseModel):
    metric_name: str
    computed_value: Any
    formula_expression: str
    execution_tier: int  # Tier 1 (Hardcoded), Tier 2 (Cache), Tier 3 (LLM String Fallback)
    inputs_referenced: List[str]

class ForensicMatrix(BaseModel):
    piotroski_f_score: int
    beneish_m_score: float
    ohlson_o_score_probability: float
    merton_distance_to_default: Optional[float]

class ValuationMatrix(BaseModel):
    deterministic_dcf_value: float
    monte_carlo_p10_floor: float
    monte_carlo_p50_median: float
    monte_carlo_p90_ceiling: float
    simulation_seed: int

class AnalysisOutput(BaseModel):
    status: str = "SUCCESS"
    forensic_matrix: ForensicMatrix
    valuation_matrix: ValuationMatrix
    operational_ratios: Dict[str, float]
    audit_trail: List[AuditEntry]

class DueDiligenceState(TypedDict):
    # Inputs
    ticker: str
    raw_docs: Optional[List[str]]
    simulate_ingestion_failure: Optional[bool]

    # Ingestion Output
    normalized_financial_data: Optional[Dict[str, Any]]
    validation_status: Optional[str]
    reparse_count: Optional[int]

    # Market Intel Output (from Node 4, parallel to Node 3)
    market_intelligence_data: Optional[Dict[str, Any]]
    competitor_data: Optional[List[Dict[str, Any]]]
    peer_comparison_table: Optional[List[Dict[str, Any]]]

    # Analysis Output (Node 2)
    analysis_output: Optional[Dict[str, Any]]

    # Risk Output (Node 3)
    risk_tags: Optional[List[Dict[str, Any]]]
    overall_risk_score: Optional[str]

    # HITL Analyst Overrides
    analyst_overrides: Optional[Dict[str, Any]]

    # Memo Output (Node 5)
    memo_path: Optional[str]
    excel_path: Optional[str]
    recommendation: Optional[str]
    audit_log: Optional[List[str]]
