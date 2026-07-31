# Financial Due Diligence System - Autonomous Financial Companion

An autonomous due diligence system for financial analysis, credit risk modeling, SEC EDGAR filing ingestion, and narrative report generation powered by multi-agent architectures (LangGraph) and LLMs.

---

## 📁 Repository Structure

```
.
├── backend/                  # Core backend application files
│   ├── main.py               # FastAPI entry point & API endpoints
│   ├── masterlanggraph.py    # LangGraph workflow orchestration graph
│   ├── nodes.py              # LangGraph node definitions & state schema
│   ├── ingestion_agent.py    # SEC EDGAR filing ingestion & chunking pipeline
│   ├── miagent_mcp.py        # Market intelligence MCP tools & FRED integration
│   ├── quant_web.py          # Quantitative financial extraction engine
│   ├── quant_engine_metrics.py# Edgar financial metrics extractor
│   ├── analysis_agent.py     # Piotroski F-Score, Beneish M-Score, Ohlson O-Score & Merton DCF
│   ├── consumer_analysis.py  # Qualitative narrative & Qdrant vector retrieval agent
│   ├── get_best_peer.py      # Competitor peer identification & matching pipeline
│   ├── memo_agent.py         # Automated executive memo & report builder (.md, .docx, .xlsx)
│   ├── news_fetcher.py       # Alpaca market news integration
│   ├── chart_generator.py    # Financial metric chart generation
│   ├── .env.example          # Environment variable configuration template
│   └── requirements.txt      # Python dependencies
├── .env.example              # Copy of environment configuration template
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Virtual Environment (recommended)

### 2. Environment Setup
Create a `.env` file inside the `backend/` directory or root directory based on `.env.example`:

```bash
cp backend/.env.example backend/.env
```

Set your API keys:
- `GEMINI_API_KEY`: Google Gemini API key
- `FRED_API_KEY`: Federal Reserve Economic Data API key
- `ALPACA_API_KEY` & `ALPACA_API_SECRET`: Alpaca Market Data API credentials
- `GROQ_API_KEY` & `TAVILY_API_KEY`: Peer analysis keys (optional)
- `QDRANT_URL` & `QDRANT_API_KEY`: Qdrant vector database credentials

### 3. Installation

```bash
# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 4. Running the Backend Server

```bash
cd backend
python main.py
```

The API server will run at `http://localhost:8000`.

---

## 📡 Key Endpoints

- `GET /api/run-diligence?ticker={TICKER}`: Stream full due-diligence analysis pipeline via Server-Sent Events (SSE).
- `GET /api/news?symbol={TICKER}`: Fetch financial market news for a given ticker.
