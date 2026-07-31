# The Wall Street DD - Backend Core

Welcome to the backend component of **The Wall Street DD**! This is an advanced, AI-powered financial due diligence pipeline that automates the comprehensive analysis of publicly traded companies. By orchestrating a multi-agent workflow, it performs quantitative valuation, qualitative narrative analysis, and risk assessment, returning detailed reports to the user.

## 🚀 Key Features

- **Automated Due Diligence Workflow**: Uses **LangGraph** to orchestrate multiple specialized AI agents (ingestion, analysis, charting, memo writing, etc.).
- **Real-Time Streaming API**: Built with **FastAPI**, it uses Server-Sent Events (SSE) to stream live progress of the analytical agents back to the frontend.
- **Comprehensive Artifact Generation**: Automatically generates professional artifacts for every analyzed ticker:
  - Markdown Reports (with Mermaid diagrams)
  - Microsoft Word Documents (`.docx`)
  - Excel DCF (Discounted Cash Flow) Valuation Models (`.xlsx`)
  - Chart Images (PNGs for KPI metrics, margins, risk radar, etc.)
- **Model Context Protocol (MCP)**: Includes a FastMCP server (`server.py`) exposing market intelligence tools like peer comparison and ratio extraction to external MCP clients.
- **Robust Financial Modeling**: Calculates intrinsic value via Monte Carlo DCF simulations and performs fraud/risk checks (Piotroski F-Score, Beneish M-Score, Ohlson O-Score, Merton Distance to Default).

## 🛠️ Technology Stack

- **Framework**: FastAPI (Python)
- **AI / Agentic Workflow**: LangGraph, Google GenAI (Gemini), Groq
- **Financial Data & APIs**: yfinance, edgartools, fredapi, Alpaca (for news)
- **MCP**: mcp, FastMCP
- **Data Science**: pandas, numpy, scikit-learn, networkx

## 📋 Prerequisites

- **Python 3.10+**
- API Keys for the AI models and data providers.

### Environment Variables
Create a `.env` file in the root of the `backend_core` directory and configure the following keys (based on your system requirements):

```env
# Required for the main analysis pipeline
GEMINI_API_KEY=your_google_gemini_key

# Other potential keys based on integrations
GROQ_API_KEY=your_groq_key
# ALPACA_API_KEY=... (If required for news fetching)
# ALPACA_SECRET_KEY=...
```

## ⚙️ Setup and Installation

1. **Navigate to the Backend Directory**:
   ```bash
   cd backend_core
   ```

2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment**:
   - **Windows**:
     ```powershell
     .\venv\Scripts\activate
     ```
   - **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 🏃‍♂️ Running the Application Locally

### 1. The Main Due Diligence API (FastAPI)
This server runs the LangGraph workflows and serves the frontend.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- The API will be accessible at: `http://localhost:8000`
- API documentation (Swagger) is available at: `http://localhost:8000/docs`

### 2. The MCP Server (Optional)
If you want to run the standalone MCP (Model Context Protocol) server for market intelligence tools.

```bash
python server.py
```
*(By default, it will run an SSE transport MCP server on port 8000, or whatever is specified in the `PORT` env var).*

## 🔌 Core API Endpoints

- `GET /api/run-diligence?ticker={SYMBOL}`
  - **Description**: Triggers the entire LangGraph due diligence pipeline for a given stock ticker. Returns a Server-Sent Events (`text/event-stream`) stream containing node-by-node execution progress, and eventually the full markdown report, along with paths to the generated Word/Excel files.
- `GET /api/news?symbol={SYMBOL}`
  - **Description**: Fetches the latest relevant news for a given stock symbol using Alpaca.

## 📂 Output Artifacts Directory

When you run a due diligence report, the generated artifacts are automatically stored in the `outputs/{TICKER}/` directory. The FastAPI server statically mounts this directory so that the frontend can easily download or display the files:

- `outputs/{TICKER}/{TICKER}.md` (Markdown Summary)
- `outputs/{TICKER}/{TICKER}_due_diligence.docx` (Full Word Report)
- `outputs/{TICKER}/{TICKER}_dcf_model.xlsx` (Excel DCF Model)
- `outputs/{TICKER}/charts/` (Generated visualizations)

## 🏗️ Architecture

- `main.py`: FastAPI application entry point, routing, and SSE streaming logic.
- `masterlanggraph.py` & `nodes.py`: Defines the LangGraph state machine and the individual agent tasks.
- `*_agent.py` (e.g., `analysis_agent.py`, `ingestion_agent.py`, `memo_agent.py`): Specialized LLM-powered nodes handling specific tasks.
- `chart_generator.py`: Generates the matplotlib charts based on financial data.
- `quant_engine_metrics.py` & `get_ratios.py`: Handles quantitative data, Monte Carlo DCF valuations, and risk scoring models.
