import json
import asyncio
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from masterlanggraph import build_graph
from news_fetcher import fetch_alpaca_news
from get_best_peer import get_best_peers

app = FastAPI(title="The Wall Street DD - Due Diligence API")

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Read Gemini API key from environment (falls back to hardcoded for local dev)
GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AQ.Ab8RN6KVewqbkCQ_dyxNcUGGllh9J4XkmRk3R5AMN1TEuLQgeg",
)

output_dir_static = Path(__file__).parent / "outputs"
output_dir_static.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(output_dir_static)), name="outputs")

# Compile graph once
graph = build_graph()


class DiligenceRequest(BaseModel):
    ticker: str
    gemini_api_key: str = GEMINI_API_KEY


def get_initial_state(ticker: str, gemini_api_key: str = ""):
    return {
        "ticker": ticker,
        "gemini_api_key": gemini_api_key or GEMINI_API_KEY,
        "revenue_latest": None,
        "revenue_previous": None,
        "cogs_latest": None,
        "cogs_previous": None,
        "gross_profit_latest": None,
        "gross_profit_previous": None,
        "sga_expenses_latest": None,
        "sga_expenses_previous": None,
        "depreciation_amortization_latest": None,
        "depreciation_amortization_previous": None,
        "net_income_latest": None,
        "net_income_previous": None,
        "net_income_continuing_ops_latest": None,
        "net_income_continuing_ops_previous": None,
        "operating_income_latest": None,
        "operating_income_previous": None,
        "interest_expense_latest": None,
        "interest_expense_previous": None,
        "income_tax_latest": None,
        "income_tax_previous": None,
        "operating_cash_flow_latest": None,
        "operating_cash_flow_previous": None,
        "capex_latest": None,
        "capex_previous": None,
        "current_assets_latest": None,
        "current_assets_previous": None,
        "current_liabilities_latest": None,
        "current_liabilities_previous": None,
        "cash_and_equivalents_latest": None,
        "cash_and_equivalents_previous": None,
        "receivables_latest": None,
        "receivables_previous": None,
        "inventory_latest": None,
        "inventory_previous": None,
        "gross_ppe_latest": None,
        "gross_ppe_previous": None,
        "total_assets_latest": None,
        "total_assets_previous": None,
        "total_liabilities_latest": None,
        "total_liabilities_previous": None,
        "long_term_debt_latest": None,
        "long_term_debt_previous": None,
        "short_term_debt_latest": None,
        "short_term_debt_previous": None,
        "shareholders_equity_latest": None,
        "shareholders_equity_previous": None,
        "retained_earnings_latest": None,
        "retained_earnings_previous": None,
        "working_capital_latest": None,
        "working_capital_previous": None,
        "common_shares_outstanding_latest": None,
        "common_shares_outstanding_previous": None,
        "current_equity_price": None,
        "market_capitalization": None,
        "historical_equity_volatility_252d": None,
        "risk_free_rate": None,
        "gnp_deflator": None,
        "piotroski_f_score": None,
        "beneish_m_score": None,
        "ohlson_o_score_probability": None,
        "merton_distance_to_default": None,
        "deterministic_dcf_value": None,
        "monte_carlo_p10_floor": None,
        "monte_carlo_p50_median": None,
        "monte_carlo_p90_ceiling": None,
        "metric_name": None,
        "computed_value": None,
        "formula_expression": None,
        "inputs_referenced": [],
        "risk_report": {},
        "quant_analysis": [],
        "narrative_analysis": [],
        "analysis_ri_agent": {},
        "markdown_report": "",
    }


async def generate_diligence_stream(req: DiligenceRequest):
    initial_state = get_initial_state(req.ticker, req.gemini_api_key)

    # Determine output directory (same dir as main.py)
    output_dir = Path(__file__).parent

    # Start fetching the best competitor asynchronously
    competitor_task = asyncio.create_task(get_best_peers(req.ticker))

    try:
        final_state = dict(initial_state)
        async for output in graph.astream(initial_state):
            # Output is a dict with node name as key
            node_name = list(output.keys())[0]
            final_state.update(output[node_name])

            # Yield progress event to frontend
            event_data = {
                "type": "progress",
                "node": node_name,
                "status": "done",
                "message": f"Agent '{node_name}' completed its analysis.",
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            # Allow async breathing room
            await asyncio.sleep(0.05)

        markdown_report = final_state.get("markdown_report", "")
        ticker_up = req.ticker.upper()

        # Save the report as {TICKER}.md in backend_core directory
        report_path = output_dir / f"{ticker_up}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(markdown_report)

        docx_url = f"/outputs/{ticker_up}/{ticker_up}_due_diligence.docx"
        excel_url = f"/outputs/{ticker_up}/{ticker_up}_dcf_model.xlsx"

        # Await the best competitor task
        best_competitor = None
        try:
            best_competitor = await competitor_task
        except Exception as e:
            print(f"Error fetching best competitor: {e}")

        # Yield complete event with the full report
        event_data = {
            "type": "complete",
            "report": markdown_report,
            "message": "Workflow Completed Successfully",
            "saved_to": str(report_path),
            "docx_url": docx_url,
            "excel_url": excel_url,
            "best_competitor": best_competitor,
        }
        yield f"data: {json.dumps(event_data)}\n\n"

    except Exception as e:
        error_data = {
            "type": "error",
            "message": str(e),
        }
        yield f"data: {json.dumps(error_data)}\n\n"


@app.get("/api/run-diligence")
async def run_diligence(ticker: str):
    """
    Stream the due-diligence pipeline for a given ticker symbol.
    Returns a Server-Sent Events stream.
    """
    try:
        req = DiligenceRequest(ticker=ticker, gemini_api_key=GEMINI_API_KEY)
        return StreamingResponse(
            generate_diligence_stream(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/news")
async def get_news(symbol: Optional[str] = None):
    result = await fetch_alpaca_news(symbol)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
