import os
import json
import re

import yfinance as yf
from typing import List, Dict, Any, Literal
from edgar import Company, set_identity
import time
import numpy as np
import pandas as pd
import networkx as nx
from groq import Groq
set_identity("Shiva Dubey 123shivadubey@gmail.com")
TICKER_SYMBOL = "FN"
GROQ_API_KEY = "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"
async def execute_quant_extraction_pipeline(ticker: str) -> dict:
    quant_registry = {}
    try:
        company = Company(ticker)
        financials = company.get_financials()
        if financials:
            for stmt_name, stmt_obj in [
                ("Income Statement", financials.income_statement()),
                ("Balance Sheet", financials.balance_sheet()),
                ("Cash Flow", financials.cash_flow_statement())
            ]:
                try:
                    df = stmt_obj.to_dataframe()
                    date_cols = [c for c in df.columns if re.search(r'\d{4}-\d{2}-\d{2}', str(c))]
                    core_meta = ['label', 'concept', 'parent_concept', 'is_breakdown', 'dimension_label']
                    keep_meta = [c for c in df.columns if c in core_meta]
                    
                    df_long = pd.melt(
                        df, id_vars=keep_meta, value_vars=date_cols, 
                        var_name='Report_Date', value_name='Value'
                    )
                    df_long = df_long.dropna(subset=['Value']).replace({np.nan: None})
                    quant_registry[stmt_name] = [
                        {k: v for k, v in row.items() if v is not None} 
                        for row in df_long.to_dict(orient="records")
                    ]
                except Exception as e:
                    print(f"    -> Compressing {stmt_name} failed: {e}")
    except Exception as e:
        print(f"[-] Quant Execution Error for {ticker}: {e}")
    return quant_registry
async def build_financial_knowledge_graph(quant_registry: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    canonical_nodes = [
        "Revenue", "CostOfRevenue", "GrossProfit", "ResearchAndDevelopment", 
        "SellingGeneralAndAdministrative", "DepreciationAndAmortization", "OperatingExpenses", 
        "OperatingIncome", "InterestExpense", "IncomeTaxExpense", "NetIncome",
        "CashAndEquivalents", "ShortTermInvestments", "AccountsReceivable", "Inventory", 
        "PrepaidExpenses", "CurrentAssets", "PropertyPlantAndEquipment", "IntangibleAssets", 
        "Goodwill", "LongTermInvestments", "OtherNonCurrentAssets", "TotalAssets",
        "AccountsPayable", "AccruedLiabilities", "ShortTermDebt", "CurrentLiabilities", 
        "LongTermDebt", "DeferredRevenue", "DeferredTaxLiabilities", "NonCurrentLiabilities", 
        "TotalLiabilities",
        "CommonStock", "RetainedEarnings", "AccumulatedOtherComprehensiveIncome", "ShareholdersEquity",
        "OperatingCashFlow", "CapitalExpenditures", "InvestingCashFlow", "DividendsPaid", 
        "StockRepurchases", "FinancingCashFlow", "FreeCashFlow",
        "GrossMargin", "OperatingMargin", "NetProfitMargin", "CurrentRatio", 
        "DebtToEquity", "ReturnOnAssets", "ReturnOnEquity"
    ]
    for node in canonical_nodes:
        G.add_node(node, value=None, status="Undisclosed", canonical_name=node)
    deterministic_relationships = [
        ("Revenue", "GrossProfit"), ("CostOfRevenue", "GrossProfit"),
        ("Revenue", "OperatingIncome"), ("Revenue", "NetIncome"), 
        ("ResearchAndDevelopment", "OperatingExpenses"), ("SellingGeneralAndAdministrative", "OperatingExpenses"),
        ("DepreciationAndAmortization", "OperatingExpenses"),
        ("GrossProfit", "OperatingIncome"), ("OperatingExpenses", "OperatingIncome"),
        ("OperatingIncome", "NetIncome"), ("IncomeTaxExpense", "NetIncome"), ("InterestExpense", "NetIncome"),
        ("CashAndEquivalents", "CurrentAssets"), ("ShortTermInvestments", "CurrentAssets"),
        ("AccountsReceivable", "CurrentAssets"), ("Inventory", "CurrentAssets"), ("PrepaidExpenses", "CurrentAssets"),
        ("CurrentAssets", "TotalAssets"), ("PropertyPlantAndEquipment", "TotalAssets"), 
        ("IntangibleAssets", "TotalAssets"), ("Goodwill", "TotalAssets"), 
        ("LongTermInvestments", "TotalAssets"), ("OtherNonCurrentAssets", "TotalAssets"),
        ("AccountsPayable", "CurrentLiabilities"), ("AccruedLiabilities", "CurrentLiabilities"), ("ShortTermDebt", "CurrentLiabilities"),
        ("CurrentLiabilities", "TotalLiabilities"), ("LongTermDebt", "NonCurrentLiabilities"), 
        ("DeferredRevenue", "NonCurrentLiabilities"), ("DeferredTaxLiabilities", "NonCurrentLiabilities"),
        ("NonCurrentLiabilities", "TotalLiabilities"),
        ("CommonStock", "ShareholdersEquity"), ("RetainedEarnings", "ShareholdersEquity"), ("AccumulatedOtherComprehensiveIncome", "ShareholdersEquity"),
        ("TotalAssets", "TotalLiabilities"), ("ShareholdersEquity", "TotalAssets"), ("TotalLiabilities", "ShareholdersEquity"),
        ("NetIncome", "RetainedEarnings"),        
        ("NetIncome", "OperatingCashFlow"),         
        ("DepreciationAndAmortization", "OperatingCashFlow"), 
        ("OperatingCashFlow", "FreeCashFlow"),
        ("CapitalExpenditures", "FreeCashFlow"),
        ("CapitalExpenditures", "PropertyPlantAndEquipment"), 
        ("CapitalExpenditures", "InvestingCashFlow"),
        ("StockRepurchases", "FinancingCashFlow"),
        ("DividendsPaid", "FinancingCashFlow"),
        ("CashAndEquivalents", "OperatingCashFlow"), 
        ("ShortTermDebt", "LongTermDebt"),           
        ("TotalLiabilities", "OperatingCashFlow"),   
        ("GrossProfit", "GrossMargin"), ("Revenue", "GrossMargin"),
        ("OperatingIncome", "OperatingMargin"), ("Revenue", "OperatingMargin"),
        ("NetIncome", "NetProfitMargin"), ("Revenue", "NetProfitMargin"),
        ("CurrentAssets", "CurrentRatio"), ("CurrentLiabilities", "CurrentRatio"),
        ("TotalLiabilities", "DebtToEquity"), ("ShareholdersEquity", "DebtToEquity"),
        ("NetIncome", "ReturnOnAssets"), ("TotalAssets", "ReturnOnAssets"),
        ("NetIncome", "ReturnOnEquity"), ("ShareholdersEquity", "ReturnOnEquity"),
        ("Revenue", "TotalAssets"), ("Revenue", "TotalLiabilities"), ("Revenue", "OperatingCashFlow"),
        ("NetIncome", "TotalAssets"), ("NetIncome", "TotalLiabilities"), ("NetIncome", "FreeCashFlow"),
        ("CashAndEquivalents", "TotalLiabilities"), ("CashAndEquivalents", "LongTermDebt")
    ]
    G.add_edges_from(deterministic_relationships)
    taxonomy_matrix = {
        "Revenue": ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        "CostOfRevenue": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
        "GrossProfit": ["GrossProfit"],
        "ResearchAndDevelopment": ["ResearchAndDevelopmentExpense"],
        "SellingGeneralAndAdministrative": ["SellingGeneralAndAdministrativeExpense"],
        "DepreciationAndAmortization": ["DepreciationDepletionAndAmortization"],
        "OperatingExpenses": ["OperatingExpenses"],
        "OperatingIncome": ["OperatingIncomeLoss"],
        "InterestExpense": ["InterestExpense", "InterestExpenseDebt"],
        "IncomeTaxExpense": ["IncomeTaxExpenseBenefit"],
        "NetIncome": ["NetIncomeLoss"],
        "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue"],
        "ShortTermInvestments": ["ShortTermInvestments", "AvailableForSaleSecuritiesCurrent"],
        "AccountsReceivable": ["AccountsReceivableNetCurrent", "AccountsReceivable"],
        "Inventory": ["InventoryNet"],
        "PrepaidExpenses": ["PrepaidExpenseAndOtherAssetsCurrent"],
        "CurrentAssets": ["AssetsCurrent"],
        "PropertyPlantAndEquipment": ["PropertyPlantAndEquipmentNet"],
        "IntangibleAssets": ["IntangibleAssetsNetExcludingGoodwill"],
        "Goodwill": ["Goodwill"],
        "TotalAssets": ["Assets"],
        "AccountsPayable": ["AccountsPayableCurrent"],
        "AccruedLiabilities": ["AccruedLiabilitiesCurrent"],
        "CurrentLiabilities": ["LiabilitiesCurrent"],
        "LongTermDebt": ["LongTermDebtNoncurrent", "LongTermDebt"],
        "DeferredRevenue": ["ContractWithCustomerLiabilityNoncurrent"],
        "TotalLiabilities": ["Liabilities"],
        "RetainedEarnings": ["RetainedEarningsAccumulatedDeficit"],
        "CommonStock": ["CommonStockValue"],
        "ShareholdersEquity": ["StockholdersEquity"],
        "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
        "CapitalExpenditures": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "InvestingCashFlow": ["NetCashProvidedByUsedInInvestingActivities"],
        "StockRepurchases": ["PaymentsForRepurchaseOfCommonStock"],
        "DividendsPaid": ["PaymentsOfDividendsCommonStock"],
        "FinancingCashFlow": ["NetCashProvidedByUsedInFinancingActivities"],
    }
    all_records = []
    for lines in quant_registry.values():
        all_records.extend(lines)
    if not all_records: return G
    unique_dates = sorted(list(set(r['Report_Date'] for r in all_records if 'Report_Date' in r)), reverse=True)
    latest_date = unique_dates[0] if unique_dates else None
    G.graph['reporting_date'] = latest_date
    for record in all_records:
        if record.get('Report_Date') != latest_date: continue 
        concept = record.get('concept', '')
        if not concept: continue
            
        concept_clean = re.split(r'[:_]', concept)[-1]
        value = record.get('Value')
        if pd.isna(value) or value in ['', 'N/A']: continue
            
        try:
            cleaned_val = float(value) if not isinstance(value, str) else float(re.sub(r'[^\d\.\-]', '', value))
        except: continue
        for canonical_name, aliases in taxonomy_matrix.items():
            if concept_clean in aliases:
                current_val = G.nodes[canonical_name]['value']
                if current_val is not None and abs(cleaned_val) <= abs(current_val):
                    continue 
                G.nodes[canonical_name]['value'] = cleaned_val
                G.nodes[canonical_name]['status'] = "Disclosed"
                break
    return G
async def run_yfinance_fallback_layer(G: nx.DiGraph, ticker: str) -> nx.DiGraph:
    yf_mapping = {
        "TotalAssets": ["Total Assets"], "TotalLiabilities": ["Total Liabilities Net Minority Interest"],
        "ShareholdersEquity": ["Stockholders Equity"], "CurrentAssets": ["Current Assets"],
        "CurrentLiabilities": ["Current Liabilities"], "CashAndEquivalents": ["Cash And Cash Equivalents"],
        "AccountsReceivable": ["Accounts Receivable", "Receivables", "Net Receivables"], 
        "Inventory": ["Inventory"], "PropertyPlantAndEquipment": ["Net PPE"],
        "LongTermDebt": ["Long Term Debt"], "Revenue": ["Total Revenue"],
        "GrossProfit": ["Gross Profit"], "OperatingExpenses": ["Operating Expense"],
        "OperatingIncome": ["Operating Income"], "NetIncome": ["Net Income"],
        "OperatingCashFlow": ["Operating Cash Flow"], "FreeCashFlow": ["Free Cash Flow"],
        "CapitalExpenditures": ["Capital Expenditure"]
    }
    try:
        yf_ticker = yf.Ticker(ticker)
        yf_bs = yf_ticker.balance_sheet
        yf_is = yf_ticker.financials
        yf_cf = yf_ticker.cashflow
        for node, yf_labels in yf_mapping.items():
            if G.has_node(node) and G.nodes[node]['value'] is None:
                for target_df in [yf_bs, yf_is, yf_cf]:
                    for label in yf_labels:
                        if label in target_df.index:
                            val = target_df.loc[label].iloc[0]
                            if not pd.isna(val):
                                G.nodes[node]['value'] = float(val)
                                G.nodes[node]['status'] = "Disclosed (yfinance Fallback)"
                                break
                    if G.nodes[node]['value'] is not None: break
    except Exception as e:
        print(f"[-] yfinance fallback failed: {e}")
    return G
def calculate_derived_ratios(G: nx.DiGraph) -> nx.DiGraph:
    def safe_div(n, d): return float(n) / float(d) if d and d != 0 else None
    vals = {node: G.nodes[node]['value'] for node in G.nodes()}
    calcs = {
        "GrossMargin": safe_div(vals.get("GrossProfit"), vals.get("Revenue")),
        "OperatingMargin": safe_div(vals.get("OperatingIncome"), vals.get("Revenue")),
        "NetProfitMargin": safe_div(vals.get("NetIncome"), vals.get("Revenue")),
        "CurrentRatio": safe_div(vals.get("CurrentAssets"), vals.get("CurrentLiabilities")),
        "DebtToEquity": safe_div(vals.get("TotalLiabilities"), vals.get("ShareholdersEquity")),
        "ReturnOnAssets": safe_div(vals.get("NetIncome"), vals.get("TotalAssets")),
        "ReturnOnEquity": safe_div(vals.get("NetIncome"), vals.get("ShareholdersEquity")),
    }
    if G.nodes["FreeCashFlow"]['value'] is None and vals.get("OperatingCashFlow") is not None and vals.get("CapitalExpenditures") is not None:
        # Note: CapEx is usually a negative number in cash flow, so  i am adding  it. 
        G.nodes["FreeCashFlow"]['value'] = vals["OperatingCashFlow"] + vals["CapitalExpenditures"]
        G.nodes["FreeCashFlow"]['status'] = "Derived internally"
    for node, value in calcs.items():
        if value is not None:
            G.nodes[node]['value'] = value
            G.nodes[node]['status'] = "Derived via Python Engine"
    return G

def get_egocentric_subgraph_context(G: nx.DiGraph, target_node: str) -> dict:
    if not G.has_node(target_node): return {}
    neighbors = list(G.successors(target_node)) + list(G.predecessors(target_node))
    neighborhood_data = {n: {"value": G.nodes[n]['value'], "status": G.nodes[n]['status']} for n in neighbors}
    return {
        "target_metric": target_node,
        "target_value": G.nodes[target_node]['value'],
        "connected_structural_metrics": neighborhood_data
    }
def analyze_node_via_groq(client: Groq, subgraph_context: dict) -> dict:
    if subgraph_context.get("target_value") is None:
        return {"health_score": None, "assessment": "Skipped. Metric undisclosed.", "risk_flag": False}

    prompt = f"""You are an elite quantitative financial analyst evaluating a complex, multi-branched corporate financial network.
    CONTEXT METRIC CLUSTER:
    {json.dumps(subgraph_context, indent=2)}
    CRITICAL RULES:
    1. RELY ON PYTHON RATIOS: You do not need to calculate complex math. Rely on the provided connected metrics (like CurrentRatio, GrossMargin) which have been flawlessly pre-computed by a Python engine.
    2. IGNORE SYSTEM METADATA: Ignore tags like "yfinance Fallback" or "Derived via Python Engine". Treat the numbers as truth.
    3. UNDERSTAND TECH/SCALE: High margins are POSITIVE indicators of a moat. Massive Cash balances relative to Debt are excellent.
    4. CASH FLOW DIRECTIONS: A negative Capital Expenditure or negative Investing Cash Flow means the company is investing heavily in infrastructure (CapEx). A negative Stock Repurchase or Financing Cash Flow means the company is returning capital to shareholders. DO NOT flag these healthy negative outflows as financial risk.
    OUTPUT FORMAT REQUIREMENTS (Raw JSON only, no markdown):
    {{
        "health_score": <int 1-10>,
        "assessment": "<2-sentence sharp conceptual audit summary>",
        "risk_flag": <true or false. ONLY true for severe financial imbalances>
    }}"""
    try:
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a precise, mathematically rigorous financial agent."},
                      {"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", temperature=0.0, response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        return {"health_score": None, "assessment": f"LLM error: {str(e)}", "risk_flag": True}
def run_pipeline(ticker: str, groq_api_key: str):
    client = Groq(api_key=groq_api_key)
    raw_quant_data = execute_quant_extraction_pipeline(ticker)
    G = build_financial_knowledge_graph(raw_quant_data)
    G = run_yfinance_fallback_layer(G, ticker)
    G = calculate_derived_ratios(G) # The Math Engine executes here
    final_audit_ledger = {}
    for node in G.nodes():
        if G.nodes[node]['value'] is None: continue
        context = get_egocentric_subgraph_context(G, node)
        analysis = analyze_node_via_groq(client, context)
        final_audit_ledger[node] = {"value": G.nodes[node]['value'], "audit": analysis}
        time.sleep(0.2) 
    print(json.dumps(final_audit_ledger, indent=2))
    return final_audit_ledger
if __name__ == "__main__":
        run_pipeline(ticker=TICKER_SYMBOL, groq_api_key=GROQ_API_KEY)
