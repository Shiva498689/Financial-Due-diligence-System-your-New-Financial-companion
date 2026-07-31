from langgraph.graph import StateGraph, START, END
from nodes import (
    AgentState,
    ingestion_node,
    miAgentnode,
    quant_web_node,
    narrative_analysis_node,
    Analysis_agent_node,
    Risk_flagging_node,
    report_generation_node,
)
def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("ingestion", ingestion_node)
    builder.add_node("market_intelligence", miAgentnode)
    builder.add_node("quant_web", quant_web_node)
    builder.add_node("narrative", narrative_analysis_node)
    builder.add_node("analysis", Analysis_agent_node)
    builder.add_node("risk_flagging", Risk_flagging_node)
    builder.add_node("report_generation", report_generation_node)
    builder.add_edge(START, "ingestion")
    builder.add_edge(START, "market_intelligence")
    builder.add_edge("ingestion", "quant_web")
    builder.add_edge("market_intelligence", "quant_web")
    builder.add_edge("ingestion", "narrative")
    builder.add_edge("market_intelligence", "narrative")
    builder.add_edge("ingestion", "analysis")
    builder.add_edge("market_intelligence", "analysis")
    builder.add_edge("quant_web", "risk_flagging")
    builder.add_edge("narrative", "risk_flagging")
    builder.add_edge("analysis", "risk_flagging")
    builder.add_edge("risk_flagging", "report_generation")
    builder.add_edge("report_generation", END)
    return builder.compile()