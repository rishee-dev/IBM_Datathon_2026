# SentinelZ AI - FastAPI Backend Foundation

The Python backend for **SentinelZ AI**, built for the IBM Z Datathon 2026.
It exposes typed REST endpoints matching the enterprise Next.js dashboard client contracts.

---

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application, CORS, exception handlers, router registry
│   ├── config.py            # Environment-driven settings (pydantic-settings) & IBM Z flags
│   ├── schemas.py           # Typed Pydantic models aligning with lib/api.ts
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── ibm_z.py         # IBM Z Adapter Interface, Real REST Adapter & Local/Mock Adapters
│   ├── engine/              # Risk Decision Engine & Rule Thresholds
│   ├── ml/                  # Random Forest & Logistic Regression ML Predictor
│   ├── repository/          # SQLite persistence layer with provenance tracking
│   ├── services/            # Transaction processing service & simulation orchestrator
│   └── routes/
│       ├── __init__.py
│       ├── health.py        # GET /api/health (system status & honest IBM Z adapter disclosure)
│       ├── transactions.py  # GET /api/transactions, GET /api/transactions/{id}, POST /api/transactions/simulate
│       ├── predictions.py   # POST /api/predict, GET /api/model/performance
│       ├── alerts.py        # GET /api/alerts
│       ├── metrics.py       # GET /api/metrics
│       └── audit.py         # GET /api/audit
├── tests/
│   ├── test_health.py       # Automated tests for health and IBM Z adapter status
│   ├── test_schemas.py      # Automated tests for schemas and validation
│   ├── test_ml_pipeline.py  # Model training and prediction tests
│   ├── test_decision_engine.py
│   ├── test_transaction_service.py
│   ├── test_sqlite_repo.py
│   ├── test_live_integration.py
│   ├── test_dashboard_flow.py
│   └── test_ibm_z_adapter.py # Stage 9 IBM Z Adapter Contract & Integrity Tests (11 tests)
├── requirements.txt         # Core dependencies
└── README.md                # Backend documentation and developer runbook
```

---

## API Contracts & Status (Stage 9)

| Method | Endpoint | Description | Status in Stage 9 |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System uptime, health, model state, IBM Z adapter state | Active (Reports IBM Z configuration & capabilities) |
| `GET` | `/api/transactions` | Lists transactions with pagination, filtering & `processedBy` | Active (SQLite persistent) |
| `GET` | `/api/transactions/{id}` | Individual transaction with risk breakdown & provenance | Active |
| `POST` | `/api/predict` | Real-time risk scoring | Active (Random Forest ML predictor) |
| `POST` | `/api/transactions/simulate` | End-to-end simulation pipeline | Active (Routed via adapter boundary) |
| `GET` | `/api/alerts` | Alert prioritization queue | Active |
| `GET` | `/api/metrics` | Real-time telemetry, accuracy, and latency metrics | Active |
| `GET` | `/api/model/performance` | Model evaluation benchmarks & confusion matrix | Active |
| `GET` | `/api/audit` | Audit trail of security and system actions | Active |

---

## Quickstart Runbook (Windows PowerShell)

### 1. Create Virtual Environment
```powershell
python -m venv backend\.venv
```

### 2. Activate Virtual Environment & Install Dependencies
```powershell
backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

### 3. Run Automated Tests
```powershell
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\pytest backend\tests -v
```

### 4. Start the FastAPI Development Server
```powershell
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI Swagger UI is available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 5. Verify the Health Endpoint
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
```
