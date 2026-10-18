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
│   ├── config.py            # Environment-driven settings (pydantic-settings)
│   ├── schemas.py           # Typed Pydantic models aligning with lib/api.ts
│   └── routes/
│       ├── __init__.py
│       ├── health.py        # GET /api/health (system status & honest IBM Z adapter disclosure)
│       ├── transactions.py  # GET /api/transactions, GET /api/transactions/{id}, POST /api/transactions/simulate
│       ├── predictions.py   # POST /api/predict, GET /api/model/performance
│       ├── alerts.py        # GET /api/alerts
│       ├── metrics.py       # GET /api/metrics
│       └── audit.py         # GET /api/audit
├── tests/
│   ├── __init__.py
│   ├── test_health.py       # Automated tests for health, IBM Z adapter status, CORS
│   └── test_schemas.py      # Automated tests for schemas, validation, 404/422/503 handling
├── requirements.txt         # Core dependencies (FastAPI, Pydantic, Uvicorn, Pytest, HTTPX)
└── README.md                # Backend documentation and developer runbook
```

---

## API Contracts & Status (Stage 2)

| Method | Endpoint | Description | Status in Stage 2 |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System uptime, health, model state, IBM Z adapter state | Active (Reports IBM Z as unconfigured) |
| `GET` | `/api/transactions` | Lists transactions (supports `riskLevel`, `channel`, `limit`) | Active (Conforms to `Transaction[]`) |
| `GET` | `/api/transactions/{id}` | Fetches individual transaction by ID (404 on not found) | Active |
| `POST` | `/api/predict` | Validates payload; runs risk inference | Active Validation (Returns 503 pending Stage 4) |
| `POST` | `/api/transactions/simulate` | End-to-end simulation pipeline | Pending Stage 6 (Returns 503) |
| `GET` | `/api/alerts` | Alert prioritization queue | Active (Conforms to `Alert[]`) |
| `GET` | `/api/metrics` | Dashboard KPI metrics and telemetry | Active (Conforms to `Metrics`) |
| `GET` | `/api/model/performance` | Model evaluation benchmarks & disclosures | Active (Transparent `pending_evaluation`) |
| `GET` | `/api/audit` | Audit trail of security and system actions | Active (Conforms to `AuditRecord[]`) |

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
