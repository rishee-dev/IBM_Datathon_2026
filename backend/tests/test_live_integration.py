"""
Live Integration and API Verification Suite for SentinelZ AI (Stage 8).
Verifies live endpoint contracts, honest IBM Z status, telemetry aggregation,
scenario simulation, alert queue updates, audit logging, and error handling.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.repository.sqlite_repo import sqlite_repo
from app.services.transaction_service import transaction_service

client = TestClient(app)


def test_health_endpoint_honest_ibm_z_and_model_status():
    """Verify GET /api/health accurately reports model readiness and unconfigured IBM Z state."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "version" in data
    assert "loaded" in data["modelStatus"].lower()
    
    # Honest IBM Z status verification
    ibm_z = data["ibmZAdapter"]
    assert ibm_z["status"] == "unconfigured"
    assert ibm_z["connection"] == "none"
    assert "local verification mode" in ibm_z["details"].lower()


def test_metrics_telemetry_series_format_and_dynamic_counts():
    """Verify GET /api/metrics computes dynamic KPIs and truthful telemetry series."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics = response.json()

    assert metrics["transactionsProcessed"] >= 0
    assert metrics["highRiskTransactions"] >= 0
    assert metrics["alertsGenerated"] >= 0
    assert metrics["averageLatencyMs"] >= 0.0

    # Ensure volumeData and latencyData are present as real arrays
    assert isinstance(metrics["volumeData"], list)
    assert isinstance(metrics["latencyData"], list)

    for pt in metrics["latencyData"]:
        assert "time" in pt
        assert "value" in pt
        assert pt["value"] >= 0.0


def test_simulate_all_supported_scenarios():
    """Verify each supported scenario can be simulated through POST /api/transactions/simulate."""
    scenarios = [
        "normal",
        "unusual_amount",
        "velocity_burst",
        "elevated_device_risk",
        "cross_border_wire",
    ]

    for sc in scenarios:
        res = client.post("/api/transactions/simulate", json={"scenario": sc, "seed": 42})
        assert res.status_code == 200, f"Simulation failed for scenario: {sc}"
        data = res.json()

        assert data["scenario"] == sc
        assert data["transaction"]["id"].startswith("TXN-")
        assert data["transaction"]["amount"] > 0
        assert 0 <= data["transaction"]["riskScore"] <= 100
        assert data["inferenceLatencyMs"] > 0.0
        assert data["processingLatencyMs"] >= data["inferenceLatencyMs"]
        assert "advisory" in data["syntheticDisclosure"].lower()


def test_simulation_updates_kpis_alerts_and_audit():
    """Verify that simulating transactions dynamically updates metrics, alerts, and audit trail."""
    # 1. Capture initial metrics
    m_init = client.get("/api/metrics").json()
    initial_tx_count = m_init["transactionsProcessed"]

    # 2. Simulate high risk cross-border wire
    sim_res = client.post(
        "/api/transactions/simulate",
        json={"scenario": "cross_border_wire", "seed": 999}
    )
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    tx_id = sim_data["transaction"]["id"]

    # 3. Verify metrics updated
    m_updated = client.get("/api/metrics").json()
    assert m_updated["transactionsProcessed"] == initial_tx_count + 1

    # 4. Verify transaction is present in list endpoint
    tx_list_res = client.get("/api/transactions")
    assert tx_list_res.status_code == 200
    tx_ids = [t["id"] for t in tx_list_res.json()]
    assert tx_id in tx_ids

    # 5. Verify transaction can be fetched by ID
    tx_detail_res = client.get(f"/api/transactions/{tx_id}")
    assert tx_detail_res.status_code == 200
    assert tx_detail_res.json()["id"] == tx_id

    # 6. Verify audit record was logged
    audit_res = client.get("/api/audit")
    assert audit_res.status_code == 200
    audit_logs = audit_res.json()
    assert len(audit_logs) > 0
    recent_actions = [log["action"] for log in audit_logs]
    assert "TRANSACTION_PROCESSED" in recent_actions


def test_simulation_failure_when_model_unloaded(monkeypatch):
    """Verify that if the predictor model is unavailable, 503 is returned with clear detail."""
    monkeypatch.setattr(transaction_service.predictor, "model_pipeline", None)

    response = client.post("/api/transactions/simulate", json={"scenario": "normal"})
    assert response.status_code == 503
    assert "not yet trained or loaded" in response.json()["detail"].lower()


def test_model_performance_authentic_stage4_benchmarks():
    """Verify GET /api/model/performance returns authentic evaluation metrics with synthetic data disclosure."""
    response = client.get("/api/model/performance")
    assert response.status_code == 200
    perf = response.json()

    assert perf["status"] == "ready"
    assert "1.0.0" in perf["modelVersion"]
    assert perf["precision"] is not None
    assert perf["recall"] is not None
    assert perf["prAuc"] is not None
    assert "synthetic" in perf["datasetDisclosures"].lower()
