# How to Run the LedgerIQ AI Finance Controller Project

This guide provides complete instructions to set up, configure, and run both the **Backend** and **Frontend** services of **LedgerIQ**.

---

## 🏗️ Architecture & Port Mapping

| Component | Directory | Port / URL | Technology Stack |
| :--- | :--- | :--- | :--- |
| **Backend API** | `backend/` | `http://localhost:8000` | FastAPI, SQLAlchemy (Async), PostgreSQL (Neon), Cloud LLM (Kimi/Moonshot) |
| **Frontend UI** | `frontend/` | `http://localhost:3000` | Vanilla HTML5 / CSS3 / ES6 JavaScript + Three.js Particle Visualizer |

---

## 🚀 Quick Start (Running Both Services)

You will need **two terminal windows**:

### Terminal 1: Backend Server (Port 8000)

```bash
cd backend

# 1. Activate python virtual environment
source .venv/bin/activate

# 2. (Optional) Run one-time database table initialization if not already done
python scripts/init_db.py

# 3. Start the FastAPI server
python run.py
```

> **Alternative (Direct Uvicorn with hot-reload):**
> ```bash
> uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
> ```

---

### Terminal 2: Frontend Client (Port 3000)

```bash
cd frontend

# Start the local static HTTP server
python3 -m http.server 3000
```

Once running, open your web browser at:
👉 **[http://localhost:3000](http://localhost:3000)**

---

## ⚙️ 1. Backend Configuration (`backend/.env`)

Before running the backend for the first time, verify that `backend/.env` is configured with your database and LLM credentials:

```env
# Neon Serverless PostgreSQL Database Connection
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<neon-host>/<dbname>?ssl=require

# Cloud LLM Configuration (Kimi / Moonshot API for autonomous root-cause reasoning)
KIMI_API_KEY=your-kimi-api-key-here
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2-0711-preview

# Optional: Local Ollama (for offline merchant normalization fallback)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi4-mini:latest
```

---

## 🔍 2. Health Check & API Verification

With the backend running, verify connectivity:

### Health Endpoint
```bash
curl -s http://localhost:8000/health
```

Expected output:
```json
{
  "status": "ok",
  "service": "ai-finance-controller",
  "db": "connected",
  "db_error": null,
  "llm_configured": true,
  "llm_model": "kimi-k2-0711-preview"
}
```

### Interactive API Documentation
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📊 3. Running Automated E2E Benchmarks

With the backend running on port 8000, you can run the end-to-end automated benchmark in a separate terminal:

```bash
cd backend
source .venv/bin/activate
python scripts/benchmark_e2e.py
```

This automated script performs:
1. Health connectivity verification
2. Synthetic batch generation (50+ transactions across Bank, Gateway, ERP)
3. 3-tier cascade reconciliation run
4. AI root-cause diagnostics on generated exceptions
5. Forward cash flow forecasting
6. Cryptographic SHA-256 audit chain verification

---

## 🛠️ 4. Troubleshooting & FAQ

### Port 8000 is already in use (`[Errno 48] Address already in use`)
If a previous backend process is lingering in the background, terminate it:
```bash
kill -9 $(lsof -ti:8000)
```

### Port 3000 is already in use (`[Errno 48] Address already in use`)
If another process is using port 3000, terminate it:
```bash
kill -9 $(lsof -ti:3000)
```

### Resetting / Clearing Database Data
If you need to re-initialize tables from scratch:
```bash
cd backend
source .venv/bin/activate
python scripts/init_db.py
```

---

## 🎬 5. Interactive Demo Walkthrough

For step-by-step guidance on demonstrating all features (3D Hero view, Batch Ingestion, 3-Tier Reconciliation, AI Diagnostics, What-If Cash Stress Simulator, SHA-256 Audit Trail, and Copilot), refer to:
👉 **[demo.md](file:///Users/abhi/Documents/Projects/ai_finance_controller/demo.md)**