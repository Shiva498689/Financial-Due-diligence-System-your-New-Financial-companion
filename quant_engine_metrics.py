

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional, Sequence

from edgar import Company, set_identity

_IDENTITY_SET = False

set_identity("Shiva Dubey 123shivadubey@gmail.com")



@dataclass
class FinancialMetrics:
    revenue_latest: Optional[float] = None
    revenue_previous: Optional[float] = None
    cogs_latest: Optional[float] = None
    cogs_previous: Optional[float] = None
    gross_profit_latest: Optional[float] = None
    gross_profit_previous: Optional[float] = None
    sga_expenses_latest: Optional[float] = None
    sga_expenses_previous: Optional[float] = None
    depreciation_amortization_latest: Optional[float] = None
    depreciation_amortization_previous: Optional[float] = None
    net_income_latest: Optional[float] = None
    net_income_previous: Optional[float] = None
    net_income_continuing_ops_latest: Optional[float] = None
    net_income_continuing_ops_previous: Optional[float] = None
    operating_income_latest: Optional[float] = None
    operating_income_previous: Optional[float] = None
    interest_expense_latest: Optional[float] = None
    interest_expense_previous: Optional[float] = None
    income_tax_latest: Optional[float] = None
    income_tax_previous: Optional[float] = None
    operating_cash_flow_latest: Optional[float] = None
    operating_cash_flow_previous: Optional[float] = None
    capex_latest: Optional[float] = None
    capex_previous: Optional[float] = None
    current_assets_latest: Optional[float] = None
    current_assets_previous: Optional[float] = None
    current_liabilities_latest: Optional[float] = None
    current_liabilities_previous: Optional[float] = None
    cash_and_equivalents_latest: Optional[float] = None
    cash_and_equivalents_previous: Optional[float] = None
    receivables_latest: Optional[float] = None
    receivables_previous: Optional[float] = None
    inventory_latest: Optional[float] = None
    inventory_previous: Optional[float] = None
    gross_ppe_latest: Optional[float] = None
    gross_ppe_previous: Optional[float] = None
    total_assets_latest: Optional[float] = None
    total_assets_previous: Optional[float] = None
    total_liabilities_latest: Optional[float] = None
    total_liabilities_previous: Optional[float] = None
    long_term_debt_latest: Optional[float] = None
    long_term_debt_previous: Optional[float] = None
    short_term_debt_latest: Optional[float] = None
    short_term_debt_previous: Optional[float] = None
    shareholders_equity_latest: Optional[float] = None
    shareholders_equity_previous: Optional[float] = None
    retained_earnings_latest: Optional[float] = None
    retained_earnings_previous: Optional[float] = None
    working_capital_latest: Optional[float] = None
    working_capital_previous: Optional[float] = None
    common_shares_outstanding_latest: Optional[float] = None
    common_shares_outstanding_previous: Optional[float] = None
    fiscal_year_latest: Optional[int] = None
    fiscal_year_previous: Optional[int] = None
    source_tags: Optional[Dict[str, str]] = None
@dataclass
class MetricSpec:
    field_prefix: str
    synonym_group: Optional[str] = None
    statement: Optional[str] = None
    labels: Sequence[str] = ()
    raw_tags: Sequence[str] = ()
    raw_tags_first: bool = False


METRIC_SPECS: List[MetricSpec] = [
    MetricSpec(
        "revenue",
        synonym_group="revenue",
        statement="income",
        labels=["Revenue", "Total Revenue", "Net Sales", "Net Revenue"],
        raw_tags=[
            "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet", "SalesRevenueGoodsNet", "NetSales", "TotalRevenues",
        ],
    ),
    MetricSpec(
        "cogs",
        synonym_group="cost_of_revenue",
        statement="income",
        labels=["Cost of Revenue", "Cost of Goods Sold", "Cost of Sales", "Cost of Goods and Services Sold"],
        raw_tags=["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfSales"],
    ),
    MetricSpec(
        "gross_profit",
        synonym_group="gross_profit",
        statement="income",
        labels=["Gross Profit"],
        raw_tags=["GrossProfit"],
    ),
    MetricSpec(
        "sga_expenses",
        synonym_group="sga_expense",
        statement="income",
        labels=["Selling, General and Administrative Expense", "Selling General And Administration",
                "SG&A Expense", "General and Administrative Expense"],
        raw_tags=[
            "SellingGeneralAndAdministrativeExpense",
            "GeneralAndAdministrativeExpense",
            "SellingAndMarketingExpense",
        ],
    ),
    MetricSpec(
        "depreciation_amortization",
        synonym_group="depreciation_and_amortization",
        statement="cashflow",
        labels=["Depreciation & Amortization (CF)", "Depreciation, Depletion and Amortization",
                "Depreciation and Amortization", "Depreciation Expense"],
        raw_tags=[
            "DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
            "Depreciation", "AmortizationOfIntangibleAssets",
        ],
    ),
    MetricSpec(
        "net_income",
        synonym_group="net_income",
        statement="income",
        labels=["Net Income", "Net Income (Loss)", "Net Income Attributable to Parent"],
        raw_tags=["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAttributableToParent"],
    ),
    MetricSpec(
        "net_income_continuing_ops",
        statement="income",
        labels=["Income from Continuing Operations", "Net Income from Continuing Operations"],
        raw_tags=[
            "IncomeLossFromContinuingOperations",
            "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsAttributableToParent",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        ],
        raw_tags_first=True,
    ),
    MetricSpec(
        "operating_income",
        synonym_group="operating_income",
        statement="income",
        labels=["Operating Income", "Operating Income (Loss)", "Income from Operations"],
        raw_tags=["OperatingIncomeLoss"],
    ),
    MetricSpec(
        "interest_expense",
        synonym_group="interest_expense",
        statement="income",
        labels=["Interest Expense", "Interest Expense, Net"],
        raw_tags=["InterestExpense", "InterestExpenseDebt", "InterestExpenseNet"],
    ),
    MetricSpec(
        "income_tax",
        synonym_group="income_tax_expense",
        statement="income",
        labels=["Income Tax Expense", "Provision for Income Taxes", "Current Income Tax Expense"],
        raw_tags=["IncomeTaxExpenseBenefit", "CurrentIncomeTaxExpenseBenefit"],
    ),
    MetricSpec(
        "operating_cash_flow",
        synonym_group="operating_cash_flow",
        statement="cashflow",
        labels=["Net Cash from Operating Activities", "Cash Flow from Operating Activities",
                "Net Cash Provided by Operating Activities"],
        raw_tags=[
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ],
    ),
    MetricSpec(
        "capex",
        synonym_group="capex",
        statement="cashflow",
        labels=["Capital Expenditures", "Payments to Acquire Property, Plant and Equipment"],
        raw_tags=[
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForCapitalImprovements",
            "PaymentsToAcquireProductiveAssets",
        ],
    ),
    MetricSpec(
        "current_assets",
        synonym_group="total_current_assets",
        statement="balance",
        labels=["Total Current Assets"],
        raw_tags=["AssetsCurrent"],
    ),
    MetricSpec(
        "current_liabilities",
        synonym_group="total_current_liabilities",
        statement="balance",
        labels=["Total Current Liabilities"],
        raw_tags=["LiabilitiesCurrent"],
    ),
    MetricSpec(
        "cash_and_equivalents",
        synonym_group="cash_and_equivalents",
        statement="balance",
        labels=["Cash and Cash Equivalents", "Cash and Cash Equivalents, at Carrying Value"],
        raw_tags=[
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ],
    ),
    MetricSpec(
        "receivables",
        synonym_group="accounts_receivable",
        statement="balance",
        labels=["Accounts Receivable", "Accounts Receivable, Net"],
        raw_tags=[
            "AccountsReceivableNetCurrent",
            "ReceivablesNetCurrent",
            "AccountsAndOtherReceivablesNetCurrent",
        ],
    ),
    MetricSpec(
        "inventory",
        synonym_group="inventory",
        statement="balance",
        labels=["Inventory", "Inventory, Net"],
        raw_tags=["InventoryNet"],
    ),
    MetricSpec(
        "gross_ppe",
        synonym_group="property_plant_equipment",
        statement="balance",
        labels=["Property, Plant & Equipment, Gross", "Property, Plant and Equipment, Gross",
                "Property, Plant and Equipment"],
        raw_tags=["PropertyPlantAndEquipmentGross"],
        raw_tags_first=True,
    ),
    MetricSpec(
        "total_assets",
        synonym_group="total_assets",
        statement="balance",
        labels=["Total Assets"],
        raw_tags=["Assets"],
    ),
    MetricSpec(
        "total_liabilities",
        synonym_group="total_liabilities",
        statement="balance",
        labels=["Total Liabilities"],
        raw_tags=["Liabilities"],
    ),
    MetricSpec(
        "long_term_debt",
        synonym_group="long_term_debt",
        statement="balance",
        labels=["Long-Term Debt", "Long Term Debt"],
        raw_tags=["LongTermDebtNoncurrent", "LongTermDebt"],
    ),
    MetricSpec(
        "short_term_debt",
        synonym_group="short_term_debt",
        statement="balance",
        labels=["Short-Term Debt", "Current Portion of Long-Term Debt"],
        raw_tags=["ShortTermBorrowings", "LongTermDebtCurrent", "DebtCurrent"],
    ),
    MetricSpec(
        "shareholders_equity",
        synonym_group="stockholders_equity",
        statement="balance",
        labels=["Total Stockholders' Equity", "Total Equity", "Stockholders Equity",
                "Total Equity Including Noncontrolling Interest"],
        raw_tags=[
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ],
    ),
    MetricSpec(
        "retained_earnings",
        synonym_group="retained_earnings",
        statement="balance",
        labels=["Retained Earnings", "Retained Earnings (Accumulated Deficit)"],
        raw_tags=["RetainedEarningsAccumulatedDeficit"],
    ),
    MetricSpec(
        "common_shares_outstanding",
        synonym_group="common_shares_outstanding",
        statement="balance",
        labels=["Shares Outstanding", "Common Stock Shares Outstanding"],
        raw_tags=["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    ),
]

class EdgarFinancialExtractor:
    def __init__(self, ticker: str, identity: Optional[str] = None, verbose: bool = False):
        # _ensure_identity(identity)
        self.ticker = ticker.upper()
        self.verbose = verbose
        self.company = Company(self.ticker)
        if self.company is None or getattr(self.company, "not_found", False):
            raise ValueError(f"Could not find a company on EDGAR for ticker '{ticker}'")
        self.facts = self.company.get_facts()
        if self.facts is None:
            raise ValueError(
                f"No XBRL facts available for '{ticker}' on EDGAR "
                "(company may not file with the SEC, or has no XBRL data)."
            )

        self._statement_cache: Dict[str, Any] = {}
        self.fiscal_years: List[int] = self._recent_fiscal_years(n=2)
    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[{self.ticker}] {msg}")

    def _recent_fiscal_years(self, n: int = 2) -> List[int]:
        years: List[int] = []
        try:
            for entry in self.facts.available_periods():
                if entry.fiscal_period == "FY" and entry.fiscal_year not in years:
                    years.append(entry.fiscal_year)
                if len(years) >= n:
                    break
        except Exception as exc:  # pragma: no cover - defensive
            self._log(f"Could not determine fiscal years: {exc}")
        return years
    def _get_statement(self, kind: str):
        if kind in self._statement_cache:
            return self._statement_cache[kind]
        stmt = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if kind == "income":
                    stmt = self.company.income_statement(periods=4, period="annual")
                elif kind == "balance":
                    stmt = self.company.balance_sheet(periods=4, period="annual")
                elif kind == "cashflow":
                    stmt = self.company.cash_flow_statement(periods=4, period="annual")
        except Exception as exc:  # pragma: no cover - defensive
            self._log(f"Could not build {kind} statement: {exc}")
            stmt = None
        self._statement_cache[kind] = stmt
        return stmt
    def _from_synonym_group(self, group: str, fiscal_year: int) -> Optional[float]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                value = self.facts.get_concept(group, period=f"{fiscal_year}-FY")
            if value is not None:
                return float(value)
        except Exception as exc:  # pragma: no cover - defensive
            self._log(f"synonym_group '{group}' FY{fiscal_year} failed: {exc}")
        return None
    def _from_statement_labels(
        self, kind: str, labels: Sequence[str], fiscal_year: int
    ) -> Optional[float]:
        stmt = self._get_statement(kind)
        if stmt is None:
            return None
        period_label = f"FY {fiscal_year}"
        for label in labels:
            try:
                item = stmt.find_item(label=label)
            except Exception:
                item = None
            if item is not None:
                val = item.values.get(period_label)
                if val is not None:
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        continue
        return None
    def _from_raw_tags(self, tags: Sequence[str], fiscal_year: int) -> Optional[float]:
        for tag in tags:
            for variant in (tag, f"us-gaap:{tag}", f"ifrs-full:{tag}"):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        fact = self.facts.get_fact(variant, period=f"{fiscal_year}-FY")
                except Exception:
                    fact = None
                if fact is not None and fact.numeric_value is not None:
                    return float(fact.numeric_value)
        return None
    def _resolve(self, spec: MetricSpec, fiscal_year: int) -> Optional[float]:
        order = []
        if spec.raw_tags_first and spec.raw_tags:
            order.append(lambda: self._from_raw_tags(spec.raw_tags, fiscal_year))
        if spec.synonym_group:
            order.append(lambda: self._from_synonym_group(spec.synonym_group, fiscal_year))
        if spec.statement and spec.labels:
            order.append(lambda: self._from_statement_labels(spec.statement, spec.labels, fiscal_year))
        if not spec.raw_tags_first and spec.raw_tags:
            order.append(lambda: self._from_raw_tags(spec.raw_tags, fiscal_year))

        for attempt in order:
            value = attempt()
            if value is not None:
                return value
        return None

    def _fill_from_yfinance(self, metrics: FinancialMetrics) -> None:
        try:
            import yfinance as yf
            import pandas as pd
        except ImportError:
            self._log("yfinance or pandas not installed; skipping hybrid fallback.")
            return

        try:
            yt = yf.Ticker(self.ticker)
            dfs = {
                "financials": yt.financials,
                "balance_sheet": yt.balance_sheet,
                "cashflow": yt.cashflow
            }
        except Exception as e:
            self._log(f"Failed to fetch yfinance data: {e}")
            return

        YFINANCE_MAP = {
            "revenue": ("financials", "Total Revenue"),
            "cogs": ("financials", "Cost Of Revenue"),
            "gross_profit": ("financials", "Gross Profit"),
            "sga_expenses": ("financials", "Selling General And Administration"),
            "depreciation_amortization": ("cashflow", "Depreciation And Amortization"),
            "net_income": ("financials", "Net Income"),
            "operating_income": ("financials", "Operating Income"),
            "interest_expense": ("financials", "Interest Expense"),
            "income_tax": ("financials", "Tax Provision"),
            "operating_cash_flow": ("cashflow", "Operating Cash Flow"),
            "capex": ("cashflow", "Capital Expenditure"),
            "current_assets": ("balance_sheet", "Current Assets"),
            "current_liabilities": ("balance_sheet", "Current Liabilities"),
            "cash_and_equivalents": ("balance_sheet", "Cash And Cash Equivalents"),
            "receivables": ("balance_sheet", "Accounts Receivable"),
            "inventory": ("balance_sheet", "Inventory"),
            "gross_ppe": ("balance_sheet", "Gross PPE"),
            "total_assets": ("balance_sheet", "Total Assets"),
            "total_liabilities": ("balance_sheet", "Total Liabilities"),
            "long_term_debt": ("balance_sheet", "Long Term Debt"),
            "short_term_debt": ("balance_sheet", "Current Debt"),
            "shareholders_equity": ("balance_sheet", "Stockholders Equity"),
            "retained_earnings": ("balance_sheet", "Retained Earnings"),
            "common_shares_outstanding": ("balance_sheet", "Ordinary Shares Number"),
        }

        for base_field, (df_name, row_name) in YFINANCE_MAP.items():
            df = dfs.get(df_name)
            if df is None or df.empty or row_name not in df.index:
                continue
            
            if len(df.columns) > 0:
                latest_val = df.loc[row_name].iloc[0]
                if pd.notna(latest_val) and getattr(metrics, f"{base_field}_latest") is None:
                    setattr(metrics, f"{base_field}_latest", float(latest_val))
                    if metrics.source_tags is not None:
                        metrics.source_tags[f"{base_field}_latest"] = f"yfinance:{row_name}"
            
            if len(df.columns) > 1:
                prev_val = df.loc[row_name].iloc[1]
                if pd.notna(prev_val) and getattr(metrics, f"{base_field}_previous") is None:
                    setattr(metrics, f"{base_field}_previous", float(prev_val))
                    if metrics.source_tags is not None:
                        metrics.source_tags[f"{base_field}_previous"] = f"yfinance:{row_name}"

    def extract(self) -> FinancialMetrics:
        metrics = FinancialMetrics()
        source_tags: Dict[str, str] = {}

        if not self.fiscal_years:
            self._log("No fiscal years discovered; returning empty metrics.")
            return metrics

        years = self.fiscal_years[:2]
        metrics.fiscal_year_latest = years[0]
        if len(years) > 1:
            metrics.fiscal_year_previous = years[1]

        for spec in METRIC_SPECS:
            for idx, suffix in enumerate(("latest", "previous")):
                if idx >= len(years):
                    break
                fiscal_year = years[idx]
                value = self._resolve(spec, fiscal_year)
                field_name = f"{spec.field_prefix}_{suffix}"
                setattr(metrics, field_name, value)
                if value is not None:
                    source_tags[field_name] = spec.synonym_group or (
                        spec.raw_tags[0] if spec.raw_tags else (spec.labels[0] if spec.labels else "")
                    )

        metrics.source_tags = source_tags
        
        self._fill_from_yfinance(metrics)

        if metrics.current_assets_latest is not None and metrics.current_liabilities_latest is not None:
            metrics.working_capital_latest = metrics.current_assets_latest - metrics.current_liabilities_latest
        if metrics.current_assets_previous is not None and metrics.current_liabilities_previous is not None:
            metrics.working_capital_previous = metrics.current_assets_previous - metrics.current_liabilities_previous

        return metrics
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Extract financial metrics from SEC EDGAR via edgartools.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--identity", default=None, help="SEC identity string 'Name email@example.com'")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    extractor = EdgarFinancialExtractor(args.ticker, identity=args.identity, verbose=args.verbose)
    result = extractor.extract()

    out = {f.name: getattr(result, f.name) for f in fields(result)}
    print(json.dumps(out, indent=2, default=str))