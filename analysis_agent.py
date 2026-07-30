import math
from typing import Any, Dict, Optional
import numpy as np
class Tier1FormulaRegistry:

    DEFAULT_VALUES: Dict[str, float] = {

        "revenue_latest": 0.0, "revenue_previous": 0.0,
        "cogs_latest": 0.0, "cogs_previous": 0.0,
        "gross_profit_latest": 0.0, "gross_profit_previous": 0.0,
        "sga_expenses_latest": 0.0, "sga_expenses_previous": 0.0,
        "depreciation_amortization_latest": 0.0, "depreciation_amortization_previous": 0.0,
        "net_income_latest": 0.0, "net_income_previous": 0.0,
        "net_income_continuing_ops_latest": 0.0, "net_income_continuing_ops_previous": 0.0,
        "operating_income_latest": 0.0, "operating_income_previous": 0.0,
        "interest_expense_latest": 0.0, "interest_expense_previous": 0.0,
        "income_tax_latest": 0.0, "income_tax_previous": 0.0,
        "operating_cash_flow_latest": 0.0, "operating_cash_flow_previous": 0.0,
        "capex_latest": 0.0, "capex_previous": 0.0,
        "current_assets_latest": 0.0, "current_assets_previous": 0.0,
        "current_liabilities_latest": 0.0, "current_liabilities_previous": 0.0,
        "cash_and_equivalents_latest": 0.0, "cash_and_equivalents_previous": 0.0,
        "receivables_latest": 0.0, "receivables_previous": 0.0,
        "inventory_latest": 0.0, "inventory_previous": 0.0,
        "gross_ppe_latest": 0.0, "gross_ppe_previous": 0.0,
        "total_assets_latest": 0.0, "total_assets_previous": 0.0,
        "total_liabilities_latest": 0.0, "total_liabilities_previous": 0.0,
        "long_term_debt_latest": 0.0, "long_term_debt_previous": 0.0,
        "short_term_debt_latest": 0.0, "short_term_debt_previous": 0.0,
        "shareholders_equity_latest": 0.0, "shareholders_equity_previous": 0.0,
        "retained_earnings_latest": 0.0, "retained_earnings_previous": 0.0,
        "common_shares_outstanding_latest": 0.0, "common_shares_outstanding_previous": 0.0,
        "current_equity_price": 0.0,
        "market_capitalization": 0.0,
        "historical_equity_volatility_252d": 0.30,  # typical equity vol assumption
        "risk_free_rate": 0.04,                     # typical risk-free rate assumption
        "gnp_deflator": 1.0,
    }


    @classmethod
    def get(cls, state: Any, key: str, default: Optional[float] = None) -> float:
       
        value = None
        try:
            if isinstance(state, dict):
                value = state.get(key)
            else:
                value = getattr(state, key, None)
        except Exception:
            value = None

        fallback = default if default is not None else cls.DEFAULT_VALUES.get(key, 0.0)

        if value is None:
            return fallback

        try:
            value = float(value)
        except (TypeError, ValueError):
            return fallback

        if math.isnan(value) or math.isinf(value):
            return fallback

        return value
    @staticmethod
    def safe_div(num, denom, default: float = 0.0) -> float:
       
        try:
            if num is None or denom is None or denom == 0:
                return default
            result = num / denom
        except (TypeError, ZeroDivisionError, OverflowError):
            return default

        if isinstance(result, complex) or math.isnan(result) or math.isinf(result):
            return default
        return result
    @staticmethod
    def safe_log(value, default: float = 0.0) -> float:
  
        try:
            if value is None or value <= 0:
                return default
            result = math.log(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    @staticmethod
    def safe_sigmoid(y, default: float = 0.5) -> float:

        try:
            if y is None:
                return default
            if y > 700:
                return 1.0
            if y < -700:
                return 0.0
            return math.exp(y) / (1 + math.exp(y))
        except (TypeError, ValueError, OverflowError):
            return default
    @classmethod
    def calculate_monte_carlo_dcf(cls, state) -> Dict[str, float]:

        tax_rate = 0.25
        wacc = 0.08
        terminal_growth = 0.02
        rev_sigma = 0.05
        horizon = 5
        trials = 10000

        np.random.seed(42069)

        base_rev = cls.get(state, "revenue_latest")
        cogs_latest = cls.get(state, "cogs_latest")
        sga_latest = cls.get(state, "sga_expenses_latest")
        capex_latest = cls.get(state, "capex_latest")
        revenue_previous = cls.get(state, "revenue_previous")

        ebit = base_rev - cogs_latest - sga_latest

        ebit_margin = cls.safe_div(ebit, base_rev, default=0.10)

        capex_ratio = cls.safe_div(capex_latest, base_rev, default=0.03)

        revenue_growth = cls.safe_div(
            base_rev - revenue_previous,
            revenue_previous,
            default=0.05,
        )
        deterministic_cashflows = []
        revenue = base_rev

        for year in range(1, horizon + 1):
            revenue *= (1 + revenue_growth)

            fcf = (
                (revenue * ebit_margin) * (1 - tax_rate)
                - (revenue * capex_ratio)
            )

            deterministic_cashflows.append(fcf / ((1 + wacc) ** year))

        terminal_value = cls.safe_div(
            deterministic_cashflows[-1] * (1 + wacc) * (1 + terminal_growth),
            (wacc - terminal_growth),
        )

        deterministic_value = (
            sum(deterministic_cashflows)
            + cls.safe_div(terminal_value, (1 + wacc) ** horizon)
        )

        simulations = []

        for _ in range(trials):

            revenue = base_rev
            discounted = []

            for year in range(1, horizon + 1):
               
                revenue *= np.random.lognormal(mean=revenue_growth, sigma=rev_sigma)

                simulated_margin = np.random.normal(ebit_margin, 0.015)
                simulated_ebit = revenue * simulated_margin

                simulated_fcf = (
                    simulated_ebit * (1 - tax_rate)
                ) - (revenue * capex_ratio)

                discounted.append(simulated_fcf / ((1 + wacc) ** year))

            terminal = cls.safe_div(
                discounted[-1] * (1 + wacc) * (1 + terminal_growth),
                (wacc - terminal_growth),
            )

            simulations.append(sum(discounted) + cls.safe_div(terminal, (1 + wacc) ** horizon))

        simulations = np.asarray(simulations)

        return {
            "deterministic_dcf_value": float(deterministic_value),
            "monte_carlo_p10_floor": float(np.percentile(simulations, 10)),
            "monte_carlo_p50_median": float(np.percentile(simulations, 50)),
            "monte_carlo_p90_ceiling": float(np.percentile(simulations, 90)),
        }
    @classmethod
    def calculate_piotroski_f_score(cls, state) -> int:

        net_income_latest = cls.get(state, "net_income_latest")
        net_income_previous = cls.get(state, "net_income_previous")
        total_assets_latest = cls.get(state, "total_assets_latest")
        total_assets_previous = cls.get(state, "total_assets_previous")
        operating_cash_flow_latest = cls.get(state, "operating_cash_flow_latest")
        long_term_debt_latest = cls.get(state, "long_term_debt_latest")
        long_term_debt_previous = cls.get(state, "long_term_debt_previous")
        current_assets_latest = cls.get(state, "current_assets_latest")
        current_assets_previous = cls.get(state, "current_assets_previous")
        current_liabilities_latest = cls.get(state, "current_liabilities_latest")
        current_liabilities_previous = cls.get(state, "current_liabilities_previous")
        shares_latest = cls.get(state, "common_shares_outstanding_latest")
        shares_previous = cls.get(state, "common_shares_outstanding_previous")
        revenue_latest = cls.get(state, "revenue_latest")
        revenue_previous = cls.get(state, "revenue_previous")
        cogs_latest = cls.get(state, "cogs_latest")
        cogs_previous = cls.get(state, "cogs_previous")

        roa_t = cls.safe_div(net_income_latest, total_assets_latest)
        roa_prev = cls.safe_div(net_income_previous, total_assets_previous)

        cfo_t = cls.safe_div(operating_cash_flow_latest, total_assets_latest)

        f1 = int(roa_t > 0)
        f2 = int(cfo_t > 0)
        f3 = int(roa_t > roa_prev)
        f4 = int(cfo_t > roa_t)

        lev_t = cls.safe_div(long_term_debt_latest, total_assets_latest)
        lev_prev = cls.safe_div(long_term_debt_previous, total_assets_previous)
        f5 = int(lev_t < lev_prev)

        cr_t = cls.safe_div(current_assets_latest, current_liabilities_latest)
        cr_prev = cls.safe_div(current_assets_previous, current_liabilities_previous)
        f6 = int(cr_t > cr_prev)

        f7 = int(shares_latest <= shares_previous)

        gm_t = cls.safe_div(revenue_latest - cogs_latest, revenue_latest)
        gm_prev = cls.safe_div(revenue_previous - cogs_previous, revenue_previous)
        f8 = int(gm_t > gm_prev)

        at_t = cls.safe_div(revenue_latest, total_assets_latest)
        at_prev = cls.safe_div(revenue_previous, total_assets_previous)
        f9 = int(at_t > at_prev)

        return f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9
    @classmethod
    def calculate_beneish_m_score(cls, state) -> float:

        receivables_latest = cls.get(state, "receivables_latest")
        receivables_previous = cls.get(state, "receivables_previous")
        revenue_latest = cls.get(state, "revenue_latest")
        revenue_previous = cls.get(state, "revenue_previous")
        cogs_latest = cls.get(state, "cogs_latest")
        cogs_previous = cls.get(state, "cogs_previous")
        current_assets_latest = cls.get(state, "current_assets_latest")
        current_assets_previous = cls.get(state, "current_assets_previous")
        gross_ppe_latest = cls.get(state, "gross_ppe_latest")
        gross_ppe_previous = cls.get(state, "gross_ppe_previous")
        total_assets_latest = cls.get(state, "total_assets_latest")
        total_assets_previous = cls.get(state, "total_assets_previous")
        depreciation_latest = cls.get(state, "depreciation_amortization_latest")
        depreciation_previous = cls.get(state, "depreciation_amortization_previous")
        sga_latest = cls.get(state, "sga_expenses_latest")
        sga_previous = cls.get(state, "sga_expenses_previous")
        net_income_continuing_latest = cls.get(state, "net_income_continuing_ops_latest")
        operating_cash_flow_latest = cls.get(state, "operating_cash_flow_latest")
        long_term_debt_latest = cls.get(state, "long_term_debt_latest")
        long_term_debt_previous = cls.get(state, "long_term_debt_previous")

        dsri_curr = cls.safe_div(receivables_latest, revenue_latest)
        dsri_prev = cls.safe_div(receivables_previous, revenue_previous)
        dsri = cls.safe_div(dsri_curr, dsri_prev, default=1.0)

        gross_margin_prev = cls.safe_div(revenue_previous - cogs_previous, revenue_previous)
        gross_margin_curr = cls.safe_div(revenue_latest - cogs_latest, revenue_latest)
        gmi = cls.safe_div(gross_margin_prev, gross_margin_curr, default=1.0)

        aqi_curr = 1 - cls.safe_div(current_assets_latest + gross_ppe_latest, total_assets_latest)
        aqi_prev = 1 - cls.safe_div(current_assets_previous + gross_ppe_previous, total_assets_previous)
        aqi = cls.safe_div(aqi_curr, aqi_prev, default=1.0)

        sgi = cls.safe_div(revenue_latest, revenue_previous, default=1.0)

        dep_prev = cls.safe_div(depreciation_previous, gross_ppe_previous + depreciation_previous)
        dep_curr = cls.safe_div(depreciation_latest, gross_ppe_latest + depreciation_latest)
        depi = cls.safe_div(dep_prev, dep_curr, default=1.0)

        sgai_curr = cls.safe_div(sga_latest, revenue_latest)
        sgai_prev = cls.safe_div(sga_previous, revenue_previous)
        sgai = cls.safe_div(sgai_curr, sgai_prev, default=1.0)

        tata = cls.safe_div(
            net_income_continuing_latest - operating_cash_flow_latest,
            total_assets_latest,
        )

        lvgi_curr = cls.safe_div(long_term_debt_latest, total_assets_latest)
        lvgi_prev = cls.safe_div(long_term_debt_previous, total_assets_previous)
        lvgi = cls.safe_div(lvgi_curr, lvgi_prev, default=1.0)

        m_score = (
            -4.84
            + (0.920 * dsri)
            + (0.528 * gmi)
            + (0.404 * aqi)
            + (0.892 * sgi)
            + (0.115 * depi)
            - (0.172 * sgai)
            + (4.679 * tata)
            - (0.327 * lvgi)
        )

        return float(m_score)
    @classmethod
    def calculate_ohlson_o_score(cls, state) -> float:

        total_assets_latest = cls.get(state, "total_assets_latest")
        total_liabilities_latest = cls.get(state, "total_liabilities_latest")
        current_assets_latest = cls.get(state, "current_assets_latest")
        current_liabilities_latest = cls.get(state, "current_liabilities_latest")
        net_income_latest = cls.get(state, "net_income_latest")
        net_income_previous = cls.get(state, "net_income_previous")
        operating_cash_flow_latest = cls.get(state, "operating_cash_flow_latest")
        gnp_deflator = cls.get(state, "gnp_deflator")
        ta_scaled = cls.safe_log(
            cls.safe_div(total_assets_latest, gnp_deflator, default=1.0),
            default=0.0,
        )

        tl_ta = cls.safe_div(total_liabilities_latest, total_assets_latest)
        wc_ta = cls.safe_div(
            current_assets_latest - current_liabilities_latest,
            total_assets_latest,
        )

        cl_ca = cls.safe_div(current_liabilities_latest, current_assets_latest)
        oeneg = int(total_liabilities_latest > total_assets_latest)


        ni_ta = cls.safe_div(net_income_latest, total_assets_latest)

        fof_tl = cls.safe_div(operating_cash_flow_latest, total_liabilities_latest)

        intwo = int(net_income_latest < 0 and net_income_previous < 0)

        chg_ni = cls.safe_div(
            net_income_latest - net_income_previous,
            abs(net_income_latest) + abs(net_income_previous),
            default=0.0,
        )

        y = (
            -1.32
            - (0.407 * ta_scaled)
            + (6.03 * tl_ta)
            - (1.43 * wc_ta)
            + (0.0757 * cl_ca)
            - (1.72 * oeneg)
            - (2.37 * ni_ta)
            - (1.83 * fof_tl)
            + (0.285 * intwo)
            - (0.521 * chg_ni)
        )

        probability = cls.safe_sigmoid(y, default=0.5)

        return float(probability)
    @classmethod
    def calculate_merton_distance_to_default(cls, state) -> float:

        market_cap = cls.get(state, "market_capitalization")
        total_liabilities_latest = cls.get(state, "total_liabilities_latest")
        equity_volatility = cls.get(state, "historical_equity_volatility_252d")
        risk_free_rate = cls.get(state, "risk_free_rate")

        asset_value = market_cap + total_liabilities_latest

        asset_volatility = cls.safe_div(market_cap, asset_value) * equity_volatility

        numerator = (
            cls.safe_log(
                cls.safe_div(asset_value, total_liabilities_latest, default=1.0),
                default=0.0,
            )
            + (risk_free_rate - (asset_volatility ** 2) / 2)
        )

        denominator = asset_volatility

        distance_to_default = cls.safe_div(numerator, denominator)

        return float(distance_to_default)


def calculate_all_scores(state) -> Dict[str, Any]:
   
    results: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    def _safe_call(key, func):
        try:
            results[key] = func(state)
        except Exception as exc:  # noqa: BLE001 - intentionally broad: this
            # is the last line of defense for the whole pipeline.
            results[key] = None
            errors[key] = f"{type(exc).__name__}: {exc}"

    _safe_call("piotroski_f_score", Tier1FormulaRegistry.calculate_piotroski_f_score)
    _safe_call("beneish_m_score", Tier1FormulaRegistry.calculate_beneish_m_score)
    _safe_call("ohlson_o_score_probability", Tier1FormulaRegistry.calculate_ohlson_o_score)
    _safe_call("merton_distance_to_default", Tier1FormulaRegistry.calculate_merton_distance_to_default)
    _safe_call("monte_carlo_dcf", Tier1FormulaRegistry.calculate_monte_carlo_dcf)

    if errors:
        results["_errors"] = errors

    return results