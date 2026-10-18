# SentinelZ AI — Real-Time Transaction Risk Intelligence
**IBM Z Datathon 2026 Submission**  
**Technology Stack**: LinuxONE (s390x) / FastAPI / Python ML (Random Forest) / SQLite / Next.js 16 (React 19)  

---

## 1. Executive Summary

**SentinelZ AI** is a real-time transaction risk intelligence and fraud prevention platform built specifically for financial systems running on IBM zSystems and LinuxONE. Financial institutions running high-throughput transactional cores require sub-second risk scoring, strict policy decisioning, continuous telemetry, and tamper-resistant auditability prior to settlement.

SentinelZ AI pairs a high-performance **FastAPI backend** running an authentic **Scikit-Learn Machine Learning pipeline** with a modern **Next.js operational dashboard**, designed to operate natively on **IBM LinuxONE (s390x)**.

---

## 2. Key Capabilities & Architectural Pillars

- **Real-Time Machine Learning Scoring**: Scikit-Learn Random Forest model evaluating numerical velocity features and categorical payment channels.
- **Decision Policy Engine**: Multi-factor decision boundaries with transparent policy indicator derivation (e.g., cross-border anomalies, velocity bursts, high-risk merchant categories).
- **Zero Silent Fallback**: Mainframe adapter boundary strictly distinguishes local/LinuxONE execution from remote z/OS Connect banking gateways, ensuring transparent audit provenance (`processedBy: sentinelz_local` vs `ibm_z_rest`).
- **Resilient SQLite Repository**: Atomic ACID transactions with WAL mode, foreign-key cascades, and persistent audit logging.
- **Enterprise Monitoring Dashboard**: Real-time KPI telemetry, interactive transaction simulation panel, alert prioritization queue, model performance benchmarks, and live IBM Z capability indicators.

---

## 3. Repository Architecture

```
.
├── app/                         # Next.js 16 (React 19) Enterprise Dashboard
│   ├── page.tsx                 # Main operational monitoring interface
│   ├── layout.tsx               # Root application layout
│   └── globals.css              # Global styles
├── backend/                     # Python 3 / FastAPI Backend Service
│   ├── app/
│   │   ├── main.py              # FastAPI application & middleware
│   │   ├── config.py            # Pydantic settings & environment configuration
│   │   ├── schemas.py           # Typed Pydantic models aligning with frontend contracts
│   │   ├── adapters/
│   │   │   └── ibm_z.py         # IBM Z Adapter Interface (Local vs Real vs Mock)
│   │   ├── engine/
│   │   │   └── decision_engine.py # Risk decision engine & policy rules
│   │   ├── ml/
│   │   │   ├── artifacts/       # Serialized Random Forest pipeline & metadata.json
│   │   │   ├── predictor.py     # In-memory ML inference predictor
│   │   │   ├── preprocessor.py  # Leak-free feature preprocessor & data splitter
│   │   │   ├── synthetic_data.py # Stratified synthetic financial transaction generator
│   │   │   └── train.py         # Leak-free training & threshold optimization pipeline
│   │   ├── repository/
│   │   │   └── sqlite_repo.py   # Thread-safe SQLite persistence engine
│   │   ├── routes/              # Health, Transactions, Predictions, Alerts, Metrics, Audit
│   │   └── services/            # Transaction processing & scenario orchestrator
│   ├── tests/                   # 78 comprehensive pytest automated tests
│   ├── requirements.txt         # Backend Python dependencies
│   └── sentinelz.db             # Persistent SQLite database
├── docs/
│   ├── engineering_audit.md     # Baseline architecture audit & verification report
│   ├── security_review.md       # Threat modeling & security posture review
│   ├── ibm_z_architecture.md    # IBM Z integration architecture & adapter specifications
│   └── linuxone_deployment_guide.md # Step-by-step LinuxONE s390x deployment guide
└── lib/
    └── api.ts                   # Strongly typed Next.js frontend API client
```

---

## 4. Quickstart: Local Execution (Windows / macOS / Linux)

### 4.1. Start the FastAPI Backend
```bash
# In project root:
cd backend
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Run automated tests (78 tests):
pytest tests -v

# Start backend server:
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Interactive API docs available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4.2. Start the Next.js Dashboard
```bash
# In project root:
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 5. Documentation & Deployment Runbooks

- **[Baseline Engineering Audit](docs/engineering_audit.md)**: Architecture breakdown, ML benchmarks, test results, and platform verification.
- **[Application Security Review](docs/security_review.md)**: Threat modeling (STRIDE), input hygiene, SQL injection prevention, and Zero Silent Fallback policy.
- **[IBM Z Architecture Specification](docs/ibm_z_architecture.md)**: Interface boundary between local execution and mainframe z/OS Connect services.
- **[IBM LinuxONE Deployment Runbook](docs/linuxone_deployment_guide.md)**: Step-by-step s390x deployment, SSH tunneling, systemd service setup, and verification.

---

## 6. Model Evaluation & Scientific Disclosure

The machine learning model is evaluated on held-out synthetic test splits generated specifically for the IBM Z Datathon 2026:

| Metric | Held-Out Test Set (N=900) | Validation Partition (N=900) |
| :--- | :--- | :--- |
| **Model Type** | Random Forest Classifier | Random Forest Classifier |
| **Operating Threshold** | 0.450 | 0.450 |
| **PR-AUC** | **0.2197** | **0.2862** |
| **ROC-AUC** | **0.6862** | **0.7783** |
| **Precision** | **25.93%** | **40.48%** |
| **Recall** | **21.21%** | **50.00%** |
| **F1 Score** | **0.2333** | **0.4474** |
| **False Positive Rate** | **2.31%** | **2.89%** |

> [!NOTE]
> **Synthetic Data Disclosure**: Benchmarks represent evaluation on synthetic financial transactions designed to mirror real-world class imbalance (~3.7% fraud rate) and realistic channel distributions. They are demonstration benchmarks and do not represent validated production banking metrics.