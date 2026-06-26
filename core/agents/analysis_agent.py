import os
import sqlite3
import math
import httpx
import json
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
from core.schemas import AnnualFinancials, MarketIntelPayload, AnalysisOutput, ForensicMatrix, ValuationMatrix, AuditEntry
from core.firewall import DeterministicRuntime

class Tier1FormulaRegistry:
    """
    Tier 1 (Programmatic Base):
    Native, hardcoded scripts that run standard financial frameworks immediately.
    """
    @staticmethod
    def safe_div(num: float, denom: float, default: float = 0.0) -> float:
        return num / denom if denom != 0.0 else default

    @classmethod
    def calculate_pietroski_f_score(cls, hist: Dict[str, Any], t: str, t_minus_1: str) -> Tuple[int, List[Dict[str, Any]]]:
        curr, prev = hist[t], hist[t_minus_1]
        
        # Safe ratios
        roa_t = cls.safe_div(curr["net_income"], curr["total_assets"])
        roa_prev = cls.safe_div(prev["net_income"], prev["total_assets"])
        cfo_t = cls.safe_div(curr["operating_cash_flow"], curr["total_assets"])
        
        f1 = int(roa_t > 0)
        f2 = int(cfo_t > 0)
        f3 = int(roa_t > roa_prev)
        f4 = int(cfo_t > roa_t)
        
        lev_t = cls.safe_div(curr["long_term_debt"], curr["total_assets"])
        lev_prev = cls.safe_div(prev["long_term_debt"], prev["total_assets"])
        f5 = int(lev_t < lev_prev)
        
        cr_t = cls.safe_div(curr["current_assets"], curr["current_liabilities"])
        cr_prev = cls.safe_div(prev["current_assets"], prev["current_liabilities"])
        f6 = int(cr_t > cr_prev)
        
        f7 = int(curr["common_shares_outstanding"] <= prev["common_shares_outstanding"])
        
        gm_t = cls.safe_div(curr["revenue"] - curr["cogs"], curr["revenue"])
        gm_prev = cls.safe_div(prev["revenue"] - prev["cogs"], prev["revenue"])
        f8 = int(gm_t > gm_prev)
        
        at_t = cls.safe_div(curr["revenue"], curr["total_assets"])
        at_prev = cls.safe_div(prev["revenue"], prev["total_assets"])
        f9 = int(at_t > at_prev)
        
        score = sum([f1, f2, f3, f4, f5, f6, f7, f8, f9])
        
        audit = [{
            "metric_name": "pietroski_f_score",
            "computed_value": score,
            "formula_expression": "Sum(f1..f9)",
            "execution_tier": 1,
            "inputs_referenced": ["net_income", "total_assets", "operating_cash_flow", "long_term_debt", "current_assets", "current_liabilities", "common_shares_outstanding", "revenue", "cogs"]
        }]
        return score, audit

    @classmethod
    def calculate_beneish_m_score(cls, hist: Dict[str, Any], t: str, t_minus_1: str) -> Tuple[float, List[Dict[str, Any]]]:
        curr, prev = hist[t], hist[t_minus_1]
        
        # Days Sales in Receivables Index (DSRI)
        dsri_curr = cls.safe_div(curr["receivables"], curr["revenue"])
        dsri_prev = cls.safe_div(prev["receivables"], prev["revenue"])
        dsri = cls.safe_div(dsri_curr, dsri_prev, default=1.0)
        
        # Gross Margin Index (GMI)
        margin_prev = cls.safe_div(prev["revenue"] - prev["cogs"], prev["revenue"])
        margin_curr = cls.safe_div(curr["revenue"] - curr["cogs"], curr["revenue"])
        gmi = cls.safe_div(margin_prev, margin_curr, default=1.0)
        
        # Asset Quality Index (AQI)
        aqi_curr = 1.0 - cls.safe_div(curr["current_assets"] + curr["gross_ppe"], curr["total_assets"])
        aqi_prev = 1.0 - cls.safe_div(prev["current_assets"] + prev["gross_ppe"], prev["total_assets"])
        aqi = cls.safe_div(aqi_curr, aqi_prev, default=1.0)
        
        # Sales Growth Index (SGI)
        sgi = cls.safe_div(curr["revenue"], prev["revenue"], default=1.0)
        
        # Depreciation Index (DEPI)
        dep_prev = cls.safe_div(prev["depreciation_amortization"], prev["gross_ppe"] + prev["depreciation_amortization"])
        dep_curr = cls.safe_div(curr["depreciation_amortization"], curr["gross_ppe"] + curr["depreciation_amortization"])
        depi = cls.safe_div(dep_prev, dep_curr, default=1.0)
        
        # SG&A Expense Efficiency Index (SGAI)
        sgai_curr = cls.safe_div(curr["sga_expenses"], curr["revenue"])
        sgai_prev = cls.safe_div(prev["sga_expenses"], prev["revenue"])
        sgai = cls.safe_div(sgai_curr, sgai_prev, default=1.0)
        
        # Total Accruals to Total Assets (TATA)
        tata = cls.safe_div(curr["net_income_continuing_ops"] - curr["operating_cash_flow"], curr["total_assets"])
        
        # Leverage Index (LVGI)
        lvgi_curr = cls.safe_div(curr["long_term_debt"], curr["total_assets"])
        lvgi_prev = cls.safe_div(prev["long_term_debt"], prev["total_assets"])
        lvgi = cls.safe_div(lvgi_curr, lvgi_prev, default=1.0)
        
        # Beneish 8-Factor Model
        m_score = -4.84 + (0.920 * dsri) + (0.528 * gmi) + (0.404 * aqi) + (0.892 * sgi) + (0.115 * depi) - (0.172 * sgai) + (4.679 * tata) - (0.327 * lvgi)
        
        audit = [{
            "metric_name": "beneish_m_score",
            "computed_value": float(m_score),
            "formula_expression": "Beneish_8_Factor_Polynomial",
            "execution_tier": 1,
            "inputs_referenced": ["receivables", "revenue", "cogs", "current_assets", "gross_ppe", "total_assets", "depreciation_amortization", "sga_expenses", "net_income_continuing_ops", "operating_cash_flow", "long_term_debt"]
        }]
        return float(m_score), audit

    @classmethod
    def calculate_ohlson_o_score(cls, hist: Dict[str, Any], t: str, t_minus_1: str, gnp_deflator: float) -> Tuple[float, List[Dict[str, Any]]]:
        curr, prev = hist[t], hist[t_minus_1]
        
        # Standardize Total Assets scale against GNP deflator
        ta_scaled = math.log(cls.safe_div(curr["total_assets"], gnp_deflator, default=1.0))
        tl_ta = cls.safe_div(curr["total_liabilities"], curr["total_assets"])
        wc_ta = cls.safe_div(curr["current_assets"] - curr["current_liabilities"], curr["total_assets"])
        cl_ca = cls.safe_div(curr["current_liabilities"], curr["current_assets"])
        oeneg = int(curr["total_liabilities"] > curr["total_assets"])
        ni_ta = cls.safe_div(curr["net_income"], curr["total_assets"])
        fof_tl = cls.safe_div(curr["operating_cash_flow"], curr["total_liabilities"])
        intwo = int(curr["net_income"] < 0 and prev["net_income"] < 0)
        
        # YoY Net Income shift
        chg_ni = cls.safe_div(curr["net_income"] - prev["net_income"], abs(curr["net_income"]) + abs(prev["net_income"]), default=0.0)
        
        # Logit equation
        y = -1.32 - (0.407 * ta_scaled) + (6.03 * tl_ta) - (1.43 * wc_ta) + (0.0757 * cl_ca) - (1.72 * oeneg) - (2.37 * ni_ta) - (1.83 * fof_tl) + (0.285 * intwo) - (0.521 * chg_ni)
        prob = math.exp(y) / (1.0 + math.exp(y))
        
        audit = [{
            "metric_name": "ohlson_o_score",
            "computed_value": float(prob),
            "formula_expression": "exp(Y)/(1+exp(Y))",
            "execution_tier": 1,
            "inputs_referenced": ["total_assets", "total_liabilities", "current_assets", "current_liabilities", "net_income", "operating_cash_flow"]
        }]
        return float(prob), audit

    @classmethod
    def calculate_merton_dd(cls, total_liabilities: float, market_cap: float, equity_vol: float, r_f: float, horizon: float = 1.0) -> Tuple[float, List[Dict[str, Any]]]:
        # V_A = E + D
        V_A = market_cap + total_liabilities
        # Asset Volatility approximation via deleveraging
        sigma_A = cls.safe_div(market_cap, V_A) * equity_vol
        
        # BS inversion
        num = math.log(cls.safe_div(V_A, total_liabilities, default=1.0)) + (r_f - (sigma_A ** 2) / 2.0) * horizon
        den = sigma_A * math.sqrt(horizon)
        dd = cls.safe_div(num, den)
        
        audit = [{
            "metric_name": "merton_dd",
            "computed_value": float(dd),
            "formula_expression": "Black_Scholes_Structural_Inversion",
            "execution_tier": 1,
            "inputs_referenced": ["total_liabilities", "market_cap", "equity_volatility", "risk_free_rate"]
        }]
        return float(dd), audit

class StochasticEngine:
    @staticmethod
    def run_monte_carlo_dcf(
        base_rev: float,
        ebit_margin: float,
        tax_rate: float,
        capex_rev: float,
        wacc: float,
        terminal_g: float,
        rev_mu: float,
        rev_sigma: float,
        trials: int = 10000,
        horizon: int = 5,
        seed: int = 42069
    ) -> Tuple[Dict[str, float], float]:
        np.random.seed(seed)
        
        # 1. Deterministic DCF Baseline
        det_cash_flows = []
        temp_rev = base_rev
        for year in range(1, horizon + 1):
            temp_rev *= (1.0 + rev_mu)
            fcf = ((temp_rev * ebit_margin) * (1.0 - tax_rate)) - (temp_rev * capex_rev)
            det_cash_flows.append(fcf / ((1.0 + wacc) ** year))
        
        # Gordon Growth Terminal Value
        det_tv = (det_cash_flows[-1] * (1.0 + wacc) * (1.0 + terminal_g)) / (wacc - terminal_g) if wacc > terminal_g else 0.0
        det_intrinsic = sum(det_cash_flows) + (det_tv / ((1.0 + wacc) ** horizon))
        
        # 2. Stochastic Simulation
        sim_values = []
        for _ in range(trials):
            path_flows = []
            curr_rev = base_rev
            for year in range(1, horizon + 1):
                # Revenue growth following discretized GBM
                curr_rev *= np.random.lognormal(mean=rev_mu, sigma=rev_sigma)
                # Operating margin subject to normal perturbation
                sim_ebit = curr_rev * np.random.normal(ebit_margin, 0.015)
                sim_fcf = (sim_ebit * (1.0 - tax_rate)) - (curr_rev * capex_rev)
                path_flows.append(sim_fcf / ((1.0 + wacc) ** year))
            
            tv = (path_flows[-1] * (1.0 + wacc) * (1.0 + terminal_g)) / (wacc - terminal_g) if wacc > terminal_g else 0.0
            sim_values.append(sum(path_flows) + (tv / ((1.0 + wacc) ** horizon)))
            
        sim_values = np.array(sim_values)
        percentiles = {
            "p10_floor": float(np.percentile(sim_values, 10)),
            "p50_median": float(np.percentile(sim_values, 50)),
            "p90_ceiling": float(np.percentile(sim_values, 90))
        }
        return percentiles, float(det_intrinsic)

class AnalysisAgent:
    def __init__(self, db_path: str = "formula_cache.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                ticker TEXT,
                year TEXT,
                expression TEXT,
                computed_value REAL,
                PRIMARY KEY (ticker, year, expression)
            )
        """)
        conn.commit()
        conn.close()

    def get_cached_value(self, ticker: str, year: str, expression: str) -> Optional[float]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT computed_value FROM cache WHERE ticker = ? AND year = ? AND expression = ?", (ticker, year, expression))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_cached_value(self, ticker: str, year: str, expression: str, value: float):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)", (ticker, year, expression, value))
        conn.commit()
        conn.close()

    def _query_llm_for_formula(self, unstructured_query: str) -> str:
        """
        Tier 3 (LLM Fallback):
        Calls local Ollama (Qwen2.5-14B) on port 11434 to translate a description into a math expression.
        Includes a robust fallback dictionary if Ollama is unreachable.
        """
        fallback_dict = {
            "cash ratio": "(cash_and_equivalents + receivables) / current_liabilities",
            "operating profit margin": "(revenue - cogs - sga_expenses) / revenue",
            "working capital turn": "revenue / (current_assets - current_liabilities)"
        }
        
        prompt = (
            "You are a quantitative finance translation node. Output ONLY a clean, valid mathematical formula string "
            "using Python math syntax and variable names from this list: "
            "[revenue, cogs, gross_profit, sga_expenses, depreciation_amortization, net_income, "
            "net_income_continuing_ops, operating_cash_flow, capex, current_assets, current_liabilities, "
            "cash_and_equivalents, receivables, gross_ppe, total_assets, total_liabilities, long_term_debt, "
            "short_term_debt, shareholders_equity, common_shares_outstanding].\n"
            "Do NOT include any extra words, explanations, or code blocks. Just the expression.\n"
            f"Query: {unstructured_query}"
        )
        
        try:
            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:14b-instruct",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=5.0
            )
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                result = result.replace("`", "").replace("python", "").strip()
                return result
        except Exception:
            pass
            
        q_lower = unstructured_query.lower()
        for key, value in fallback_dict.items():
            if key in q_lower:
                return value
        return "(revenue - cogs) / revenue"

    def analyze(
        self,
        ticker: str,
        financial_data: Dict[str, AnnualFinancials],
        market_intel: Optional[MarketIntelPayload] = None,
        tax_rate: float = 0.25,
        wacc: float = 0.08,
        terminal_growth_rate: float = 0.02,
        projection_years: int = 5,
        force_refresh: bool = False
    ) -> AnalysisOutput:
        sorted_years = sorted(list(financial_data.keys()))
        
        # Apply ultimate balance sheet and income statement defaults if any are missing
        self._apply_ultimate_schema_fallbacks(financial_data, sorted_years)
        
        latest_year = sorted_years[-1]
        t_minus_1 = sorted_years[-2] if len(sorted_years) > 1 else latest_year
        
        # 1. Tier 1 Calculations (Piotroski, Beneish, Ohlson, Merton)
        hist_dict = {y: financial_data[y].model_dump() for y in sorted_years}
        
        f_score, f_audit = Tier1FormulaRegistry.calculate_pietroski_f_score(hist_dict, latest_year, t_minus_1)
        m_score, m_audit = Tier1FormulaRegistry.calculate_beneish_m_score(hist_dict, latest_year, t_minus_1)
        
        if not market_intel:
            market_intel = MarketIntelPayload(
                current_equity_price=10.0,
                market_capitalization=100.0,
                historical_equity_volatility_252d=0.25,
                risk_free_rate=0.04,
                gnp_deflator=1.20
            )
            
        o_score, o_audit = Tier1FormulaRegistry.calculate_ohlson_o_score(hist_dict, latest_year, t_minus_1, market_intel.gnp_deflator)
        merton_dd, merton_audit = Tier1FormulaRegistry.calculate_merton_dd(
            hist_dict[latest_year]["total_liabilities"],
            market_intel.market_capitalization,
            market_intel.historical_equity_volatility_252d,
            market_intel.risk_free_rate
        )
        
        # 2. Valuation and Monte Carlo Engine
        latest_financials = financial_data[latest_year]
        ebit = latest_financials.revenue - latest_financials.cogs - latest_financials.sga_expenses
        ebit_margin = Tier1FormulaRegistry.safe_div(ebit, latest_financials.revenue, default=0.10)
        capex_rev = Tier1FormulaRegistry.safe_div(latest_financials.capex, latest_financials.revenue, default=0.03)
        
        # Determine baseline growth rate
        revs = [financial_data[y].revenue for y in sorted_years]
        growths = [(revs[i] - revs[i-1]) / revs[i-1] for i in range(1, len(revs)) if revs[i-1] > 0]
        hist_growth = sum(growths) / len(growths) if growths else 0.05
        
        percentiles, det_intrinsic = StochasticEngine.run_monte_carlo_dcf(
            base_rev=latest_financials.revenue,
            ebit_margin=ebit_margin,
            tax_rate=tax_rate,
            capex_rev=capex_rev,
            wacc=wacc,
            terminal_g=terminal_growth_rate,
            rev_mu=hist_growth,
            rev_sigma=0.05,
            trials=10000,
            horizon=projection_years
        )
        
        # 3. Custom / Niche Ratio Evaluation (Tier 2/3 Loop)
        custom_queries = ["cash ratio", "operating profit margin", "working capital turn"]
        operational_ratios = {}
        audit_trail = []
        
        # Append Tier 1 audits
        audit_trail.extend([AuditEntry(**x) for x in f_audit])
        audit_trail.extend([AuditEntry(**x) for x in m_audit])
        audit_trail.extend([AuditEntry(**x) for x in o_audit])
        audit_trail.extend([AuditEntry(**x) for x in merton_audit])
        
        latest_context = hist_dict[latest_year]
        
        for q in custom_queries:
            cached_val = None
            if not force_refresh:
                formula_str = self._query_llm_for_formula(q)
                cached_val = self.get_cached_value(ticker, latest_year, formula_str)
                
            if cached_val is not None:
                operational_ratios[q] = cached_val
                audit_trail.append(AuditEntry(
                    metric_name=q,
                    computed_value=cached_val,
                    formula_expression=formula_str,
                    execution_tier=2,
                    inputs_referenced=[]
                ))
            else:
                formula_str = self._query_llm_for_formula(q)
                try:
                    val = DeterministicRuntime.evaluate_safely(formula_str, latest_context)
                    self.set_cached_value(ticker, latest_year, formula_str, val)
                    operational_ratios[q] = val
                    audit_trail.append(AuditEntry(
                        metric_name=q,
                        computed_value=val,
                        formula_expression=formula_str,
                        execution_tier=3,
                        inputs_referenced=[]
                    ))
                except Exception as e:
                    operational_ratios[q] = 0.0
                    audit_trail.append(AuditEntry(
                        metric_name=q,
                        computed_value=0.0,
                        formula_expression=f"FAILED: {str(e)}",
                        execution_tier=3,
                        inputs_referenced=[]
                    ))
                    
        forensic_matrix = ForensicMatrix(
            piotroski_f_score=f_score,
            beneish_m_score=m_score,
            ohlson_o_score_probability=o_score,
            merton_distance_to_default=merton_dd
        )
        
        valuation_matrix = ValuationMatrix(
            deterministic_dcf_value=det_intrinsic,
            monte_carlo_p10_floor=percentiles["p10_floor"],
            monte_carlo_p50_median=percentiles["p50_median"],
            monte_carlo_p90_ceiling=percentiles["p90_ceiling"],
            simulation_seed=42069
        )
        
        return AnalysisOutput(
            status="SUCCESS",
            forensic_matrix=forensic_matrix,
            valuation_matrix=valuation_matrix,
            operational_ratios=operational_ratios,
            audit_trail=audit_trail
        )

    def _apply_ultimate_schema_fallbacks(self, financial_data: Dict[str, AnnualFinancials], sorted_years: List[str]):
        """
        Ultimate System Defaults:
        Estimated baseline defaults if a user bypasses/skips HITL input overrides.
        """
        for year in sorted_years:
            yr_data = financial_data[year]
            
            # 1. Total Assets default
            if getattr(yr_data, "total_assets", None) is None or yr_data.total_assets <= 0.0:
                yr_data.total_assets = 1000.0
                
            # 2. Total Liabilities / Debt check
            if getattr(yr_data, "total_liabilities", None) is None or yr_data.total_liabilities <= 0.0:
                if getattr(yr_data, "shareholders_equity", None) is not None and yr_data.shareholders_equity > 0.0:
                    yr_data.total_liabilities = max(0.0, yr_data.total_assets - yr_data.shareholders_equity)
                else:
                    yr_data.total_liabilities = yr_data.total_assets * 0.40
                    
            # 3. Shareholders' Equity check
            if getattr(yr_data, "shareholders_equity", None) is None or yr_data.shareholders_equity <= 0.0:
                yr_data.shareholders_equity = max(0.0, yr_data.total_assets - yr_data.total_liabilities)
                
            # 4. Working Capital Defaults
            if getattr(yr_data, "current_assets", None) is None or yr_data.current_assets <= 0.0:
                yr_data.current_assets = yr_data.total_assets * 0.40
            if getattr(yr_data, "current_liabilities", None) is None or yr_data.current_liabilities <= 0.0:
                yr_data.current_liabilities = yr_data.total_assets * 0.20
                
            # 5. Core Operational Ratios (Income statement items)
            if getattr(yr_data, "revenue", None) is None or yr_data.revenue <= 0.0:
                yr_data.revenue = 100.0
            if getattr(yr_data, "cogs", None) is None or yr_data.cogs <= 0.0:
                yr_data.cogs = yr_data.revenue * 0.60
            if getattr(yr_data, "gross_profit", None) is None or yr_data.gross_profit <= 0.0:
                yr_data.gross_profit = yr_data.revenue - yr_data.cogs
            if getattr(yr_data, "net_income", None) is None or yr_data.net_income <= 0.0:
                yr_data.net_income = yr_data.revenue * 0.10
            if getattr(yr_data, "net_income_continuing_ops", None) is None or yr_data.net_income_continuing_ops <= 0.0:
                yr_data.net_income_continuing_ops = yr_data.net_income
            if getattr(yr_data, "operating_cash_flow", None) is None or yr_data.operating_cash_flow <= 0.0:
                yr_data.operating_cash_flow = yr_data.net_income
                
            # 6. Non-critical default fills
            if getattr(yr_data, "sga_expenses", None) is None:
                yr_data.sga_expenses = yr_data.revenue * 0.15
            if getattr(yr_data, "depreciation_amortization", None) is None:
                yr_data.depreciation_amortization = yr_data.revenue * 0.05
            if getattr(yr_data, "capex", None) is None:
                yr_data.capex = yr_data.revenue * 0.03
            if getattr(yr_data, "cash_and_equivalents", None) is None:
                yr_data.cash_and_equivalents = yr_data.current_assets * 0.20
            if getattr(yr_data, "receivables", None) is None:
                yr_data.receivables = yr_data.current_assets * 0.30
            if getattr(yr_data, "gross_ppe", None) is None:
                yr_data.gross_ppe = yr_data.total_assets * 0.50
            if getattr(yr_data, "long_term_debt", None) is None:
                yr_data.long_term_debt = yr_data.total_liabilities * 0.70
            if getattr(yr_data, "short_term_debt", None) is None:
                yr_data.short_term_debt = yr_data.total_liabilities * 0.30
            if getattr(yr_data, "common_shares_outstanding", None) is None:
                yr_data.common_shares_outstanding = 10.0
