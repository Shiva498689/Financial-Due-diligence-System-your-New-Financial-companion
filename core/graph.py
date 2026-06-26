import os
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Import Agents & Schemas
from core.agents.ingestion_agent import IngestionAgent
from core.agents.analysis_agent import AnalysisAgent
from core.agents.risk_agent import RiskAgent
from core.agents.market_intel_agent import MarketIntelAgent
from core.agents.memo_agent import MemoAgent
from core.schemas import AnnualFinancials, MarketIntelPayload, AnalysisOutput, DueDiligenceState

# Instantiate Agents
ingestion_agent = IngestionAgent()
analysis_agent = AnalysisAgent()
risk_agent = RiskAgent()
market_intel_agent = MarketIntelAgent()
memo_agent = MemoAgent()

# Node definitions
def run_ingestion(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- RUNNING INGESTION AGENT ---")
    reparse = state.get("reparse_count", 0)
    result = ingestion_agent.parse_and_validate(state, reparse_attempt=reparse)
    return result

def run_analysis(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- RUNNING ANALYSIS AGENT (AST, FORENSICS & STOCHASTIC DCF) ---")
    raw_financials = state.get("normalized_financial_data")
    if not raw_financials:
        raise ValueError("Missing normalized_financial_data in state for Analysis Node.")
        
    financial_data = {y: AnnualFinancials(**v) for y, v in raw_financials.items()}
    
    raw_market = state.get("market_intelligence_data")
    market_intel = MarketIntelPayload(**raw_market) if raw_market else None
    
    ticker = state.get("ticker", "AcmeCorp")
    result = analysis_agent.analyze(ticker, financial_data, market_intel)
    
    return {
        "analysis_output": result.model_dump()
    }

def run_risk(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- RUNNING RISK ASSESSMENT AGENT ---")
    # Risk Agent mock outputs
    result = risk_agent.assess_risks(state)
    return result

def run_market_intel(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- RUNNING MARKET INTELLIGENCE AGENT ---")
    result = market_intel_agent.fetch_market_data(state)
    return result

def run_join(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- MERGING PARALLEL BRANCHES ---")
    return {}

def run_memo(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- RUNNING MEMO GENERATION AGENT ---")
    # Apply analyst overrides if any are present from HITL
    result = memo_agent.generate_memo(state)
    return result

def run_error(state: DueDiligenceState) -> Dict[str, Any]:
    print("--- INGESTION VALIDATION FAILED REPEATEDLY - PIPELINE HALTED ---")
    return {"validation_status": "halted: validation failed repeatedly. human intervention required."}

# Conditional routing edge
def route_after_ingestion(state: DueDiligenceState) -> str:
    status = state.get("validation_status", "")
    reparse = state.get("reparse_count", 0)
    
    if status.startswith("fail"):
        if reparse < 3:
            print(f"Pydantic Validation failed. Triggering automatic re-parse attempt {reparse + 1}/3...")
            return "ingestion_node"
        else:
            return "error_node"
            
    return "analysis_node"

# Construct state graph workflow
workflow = StateGraph(DueDiligenceState)

# Add Nodes
workflow.add_node("ingestion_node", run_ingestion)
workflow.add_node("analysis_node", run_analysis)
workflow.add_node("risk_node", run_risk)
workflow.add_node("market_intel_node", run_market_intel)
workflow.add_node("join_node", run_join)
workflow.add_node("memo_node", run_memo)
workflow.add_node("error_node", run_error)

# Add Edges
workflow.add_edge(START, "ingestion_node")

# Conditional edge from Ingestion
workflow.add_conditional_edges(
    "ingestion_node",
    route_after_ingestion,
    {
        "ingestion_node": "ingestion_node",
        "analysis_node": "analysis_node",
        "error_node": "error_node"
    }
)

# Parallel Fan-out from Analysis
workflow.add_edge("analysis_node", "risk_node")
workflow.add_edge("analysis_node", "market_intel_node")

# Fan-in to Join Node
workflow.add_edge("risk_node", "join_node")
workflow.add_edge("market_intel_node", "join_node")

# Join Node to Memo Node
workflow.add_edge("join_node", "memo_node")
workflow.add_edge("memo_node", END)
workflow.add_edge("error_node", END)

# Compile Graph with Memory Checkpointer & HITL Breakpoints
checkpointer = MemorySaver()
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["analysis_node", "memo_node"]
)
