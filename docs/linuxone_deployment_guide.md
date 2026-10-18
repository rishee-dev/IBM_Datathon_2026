# SentinelZ AI — LinuxONE Community Cloud Deployment Guide
**Target Event**: IBM Z Datathon 2026  
**Architecture**: LinuxONE s390x (IBM z15 / z16)  
**Workload**: FastAPI Backend, Scikit-Learn ML Risk Predictor, SQLite Persistent Repository  

---

## 1. Overview & Deployment Architecture

This guide provides step-by-step instructions to deploy the **SentinelZ AI** transaction risk intelligence application to an **IBM LinuxONE Community Cloud** virtual machine instance running on the **s390x** mainframe architecture.

### Target Deployment Topology

```
+-----------------------------------------------------------+
|              Local Workstation (Developer / Judge)         |
|                                                           |
|   +---------------------------------------------------+   |
|   |         Next.js Enterprise Monitoring Dashboard   |   |
|   |         Port: 3000 (React 19 / TypeScript)        |   |
|   +---------------------------------------------------+   |
+-----------------------------|-----------------------------+
                              |
                              | HTTP / TLS REST API Calls
                              | (or via SSH Port-Forward Tunnel)
                              v
+-----------------------------------------------------------+
|         IBM LinuxONE Community Cloud Instance (s390x)     |
|         OS: Ubuntu 22.04 / 24.04 LTS (IBM zSystems)       |
|                                                           |
|   +---------------------------------------------------+   |
|   |   FastAPI Application Gateway (Port: 8000)        |   |
|   |   - Routers: /health, /transactions, /simulate    |   |
|   +---------------------------------------------------+   |
|                             |                             |
|                             v                             |
|   +---------------------------------------------------+   |
|   |   Machine Learning Inference Pipeline             |   |
|   |   - Random Forest Classifier (s390x native)       |   |
|   |   - Decision Policy Engine                        |   |
|   +---------------------------------------------------+   |
|                             |                             |
|                             v                             |
|   +---------------------------------------------------+   |
|   |   SQLite Persistent Storage                       |   |
|   |   - WAL mode, transaction history, audit trails   |   |
|   +---------------------------------------------------+   |
|                             |                             |
|                             v                             |
|   +---------------------------------------------------+   |
|   |   IBM Z Integration Adapter Boundary              |   |
|   |   - Local/LinuxONE simulation (active)            |   |
|   |   - Real z/OS Connect REST interface (standby)    |   |
|   +---------------------------------------------------+   |
+-----------------------------------------------------------+
```

---

## 2. Prerequisites & IBM LinuxONE Account Setup

If an IBM LinuxONE Community Cloud virtual machine has not yet been provisioned:

1. **Register for an Account**:
   - Access the **IBM LinuxONE Community Cloud** portal: [https://developer.ibm.com/community/linuxone/](https://developer.ibm.com/community/linuxone/) or [https://linuxone.cloud.marist.edu/cloud/#/login](https://linuxone.cloud.marist.edu/cloud/#/login).
   - Sign in with an IBM ID.
2. **Provision a Virtual Server**:
   - Select **Manage Instances** -> **Create**.
   - Choose image: **Ubuntu 22.04 LTS** or **Ubuntu 24.04 LTS** (`s390x` architecture).
   - Select instance size: General Purpose (e.g., 2 vCPU, 4GB RAM, 40GB Root Disk).
   - Attach your public SSH key (`~/.ssh/id_rsa.pub` or `~/.ssh/id_ed25519.pub`).
3. **Record Instance Details**:
   - Note the assigned IP address (e.g., `linuxone.example.org` or floating IP `148.100.x.x`).
   - Default SSH user: `ubuntu` (or `linux1`).

---

## 3. Preparing the LinuxONE Environment (s390x)

Once logged into the LinuxONE instance via SSH:

```bash
ssh -i ~/.ssh/your_key ubuntu@<LINUXONE_IP>
```

### Step 3.1: Verify s390x CPU Architecture
Run the following verification commands:
```bash
uname -m
# Expected output: s390x

lscpu | grep -E "Architecture|Model name|CPU\(s\)"
# Shows IBM zSystems architecture details (e.g., z15 or z16)
```

### Step 3.2: Install System Packages & Python
```bash
sudo apt update && sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    sqlite3
```

---

## 4. Deploying the Application to LinuxONE

### Step 4.1: Transfer Code to the VM
You can clone your git repository or transfer the project files from your local workstation:

**Method A: Git Clone**
```bash
git clone https://github.com/<YOUR_USER>/IBM_Datathon_2026.git ~/sentinelz-ai
cd ~/sentinelz-ai
```

**Method B: Rsync from Local Workstation**
```powershell
# From local Windows workstation PowerShell:
rsync -avz --exclude '.venv' --exclude 'node_modules' --exclude '.next' -e "ssh -i ~/.ssh/your_key" ./ ubuntu@<LINUXONE_IP>:~/sentinelz-ai/
```

### Step 4.2: Create Python Virtual Environment & Install Dependencies
```bash
cd ~/sentinelz-ai
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
```

---

## 5. Model Verification & Compatibility on s390x

### Step 5.1: Test Loading the Serialized Model
Verify that the serialized Random Forest pipeline loads cleanly on the s390x architecture:
```bash
source backend/.venv/bin/activate
PYTHONPATH=backend python3 -c "
from app.ml.predictor import predictor
print('Predictor ready:', predictor.is_ready)
print('Model Name:', predictor.metadata.get('model_name'))
print('Version:', predictor.model_version)
print('Operating Threshold:', predictor.operating_threshold)
"
```

### Step 5.2: Reproducible Native Training (If Re-serialization Needed)
If a Python version mismatch occurs between the host and VM, run the leak-free, reproducible training pipeline natively on LinuxONE. It takes ~5 seconds and preserves identical random seed (42) and metrics:
```bash
source backend/.venv/bin/activate
PYTHONPATH=backend python3 -m app.ml.train
```

### Step 5.3: Run Automated Backend Tests on LinuxONE
Execute the full test suite to guarantee zero regression:
```bash
source backend/.venv/bin/activate
PYTHONPATH=backend pytest backend/tests -v
# Expected: 78 passed
```

---

## 6. Configuring and Running the FastAPI Service

### Step 6.1: Environment Configuration
Create the `.env` file in the project directory or set environment variables:
```bash
cat << 'EOF' > backend/.env
APP_NAME="SentinelZ AI Backend (LinuxONE s390x)"
APP_VERSION="0.1.0"
DEBUG=false
API_PREFIX="/api"

# CORS Origins (Allow local Next.js frontend access)
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]

# IBM Z Mode
IBM_Z_MODE="local_simulation"
EOF
```

### Step 6.2: Start the FastAPI Service
**Interactive Run:**
```bash
source backend/.venv/bin/activate
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Production Background Service (Systemd):**
```bash
sudo cat << 'EOF' > /etc/systemd/system/sentinelz.service
[Unit]
Description=SentinelZ AI FastAPI Backend on IBM LinuxONE
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/sentinelz-ai
Environment="PYTHONPATH=/home/ubuntu/sentinelz-ai/backend"
ExecStart=/home/ubuntu/sentinelz-ai/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now sentinelz.service
sudo systemctl status sentinelz.service
```

---

## 7. Connecting the Next.js Frontend Dashboard

### Method 1: Direct Network Access (Public/Floating IP)
If port 8000 is open in the LinuxONE security group:
1. On your local machine, update `.env.local`:
   ```bash
   NEXT_PUBLIC_API_BASE_URL=http://<LINUXONE_IP>:8000
   ```
2. Re-run or restart the frontend:
   ```bash
   npm run dev
   ```

### Method 2: Encrypted SSH Tunnel (Recommended for Restricted Networks)
If inbound ports to the LinuxONE VM are restricted by firewalls, create a local SSH port forward:
```powershell
# Run from local workstation:
ssh -N -L 8000:localhost:8000 -i ~/.ssh/your_key ubuntu@<LINUXONE_IP>
```
With this tunnel active, all local dashboard requests to `http://localhost:8000` are encrypted and routed directly to the FastAPI backend running on LinuxONE.

---

## 8. Verification & Validation Checklist

Execute these verification calls against the deployed service:

```bash
# 1. Health Probe
curl -s http://localhost:8000/api/health | jq .

# 2. Model Performance
curl -s http://localhost:8000/api/model/performance | jq .

# 3. Submit Simulation Transaction
curl -s -X POST http://localhost:8000/api/transactions/simulate \
     -H "Content-Type: application/json" \
     -d '{"scenario": "cross_border_wire"}' | jq .

# 4. Verify SQLite Persistence
curl -s http://localhost:8000/api/transactions?limit=5 | jq .
```

---

## 9. Current Limitations & Honest Provenance

1. **LinuxONE vs Mainframe z/OS**:
   Running on LinuxONE provides native IBM zSystems `s390x` compute execution. This is distinct from submitting transactions to an external z/OS banking mainframe via z/OS Connect.
2. **Adapter Reporting**:
   When `IBM_Z_MODE=local_simulation`, the system transparently reports `processedBy: "sentinelz_local"` and adapter status `unconfigured`.
3. **No Silent Fallback**:
   If `IBM_Z_MODE=ibm_z` is activated and the remote host is unreachable, the system will raise an explicit `IBMZConnectionError` and will never silently substitute local inference.
