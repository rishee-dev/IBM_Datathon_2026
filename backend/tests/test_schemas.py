"""
Automated tests for schema validation, transaction lookup, alerts, metrics, and unavailable model state.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_transactions_schema_and_fields():
    """Verify transactions endpoint returns valid records conforming to lib/api.ts."""
    response = client.get("/api/transactions")
    assert response.status_code == 200
    transactions = response.json()
    assert isinstance(transactions, list)
    assert len(transactions) > 0

    first = transactions[0]
    expected_fields = [
        "id",
        "timestamp",
        "amount",
        "channel",
        "riskScore",
        "riskLevel",
        "recommendedAction",
        "indicators",
        "processingTimestamp",
    ]
    for field in expected_fields:
        assert field in first, f"Missing expected field: {field}"
    assert first["riskLevel"] in ["low", "medium", "high"]
    assert first["channel"] in ["Wire", "Card", "ACH", "Mobile"]
    assert 0 <= first["riskScore"] <= 100


def test_get_transactions_filter_by_risk_level():
    """Verify transactions can be filtered by risk level."""
    response = client.get("/api/transactions?riskLevel=high")
    assert response.status_code == 200
    transactions = response.json()
    for tx in transactions:
        assert tx["riskLevel"] == "high"


def test_get_transaction_by_id_found():
    """Verify single transaction retrieval by valid ID."""
    response = client.get("/api/transactions/TXN-849201")
    assert response.status_code == 200
    tx = response.json()
    assert tx["id"] == "TXN-849201"
    assert tx["amount"] == 24850.0


def test_get_transaction_by_id_not_found():
    """Verify 404 is returned when transaction ID does not exist."""
    response = client.get("/api/transactions/TXN-NONEXISTENT-999")
    assert response.status_code == 404
    error_data = response.json()
    assert "detail" in error_data
    assert "not found" in error_data["detail"].lower()


def test_predict_invalid_payload_negative_amount():
    """Verify validation error 422 when amount is non-positive."""
    payload = {
        "amount": -100.0,
        "channel": "Wire"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data or "detail" in data


def test_predict_invalid_payload_unsupported_channel():
    """Verify validation error 422 when channel is not in allowed enum."""
    payload = {
        "amount": 250.0,
        "channel": "Cryptocurrency"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 422


def test_predict_valid_payload_success():
    """
    Verify that when model is trained and loaded,
    POST /api/predict returns 200 with a valid PredictionResponse.
    """
    payload = {
        "amount": 2500.0,
        "channel": "Wire",
        "customerId": "CUST-1042",
        "customerBaseline": 400.0,
        "recentTransactionCount": 4,
        "time_since_previous_seconds": 45,
        "is_foreign_country": 1,
        "device_risk_score": 0.85
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["riskScore"] <= 100
    assert data["riskLevel"] in ["low", "medium", "high"]
    assert 0.0 <= data["modelProbability"] <= 1.0
    assert "recommendedAction" in data
    assert isinstance(data["indicators"], list)
    assert len(data["indicators"]) > 0
    assert data["inferenceLatencyMs"] >= 0.0
    assert data["modelVersion"] == "1.0.0"


def test_predict_returns_503_when_model_unloaded(monkeypatch):
    """Verify that when model is not loaded, 503 is returned rather than fabricated predictions."""
    from app.ml.predictor import predictor
    monkeypatch.setattr(predictor, "model_pipeline", None)
    
    payload = {
        "amount": 5000.0,
        "channel": "Wire"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 503
    data = response.json()
    assert "not yet trained or loaded" in data["detail"]


def test_transactions_simulate_success():
    """Verify simulate endpoint processes a new transaction and returns simulation response."""
    response = client.post("/api/transactions/simulate", json={"scenario": "normal", "seed": 42})
    assert response.status_code == 200
    data = response.json()
    assert "transaction" in data
    assert data["transaction"]["id"].startswith("TXN-")
    assert 0 <= data["transaction"]["riskScore"] <= 100
    assert data["scenario"] == "normal"
    assert data["processingLatencyMs"] >= 0.0
    assert data["inferenceLatencyMs"] >= 0.0


def test_transactions_simulate_returns_503_when_unloaded(monkeypatch):
    """Verify simulate endpoint returns 503 when model is unloaded."""
    from app.services.transaction_service import transaction_service
    monkeypatch.setattr(transaction_service.predictor, "model_pipeline", None)

    response = client.post("/api/transactions/simulate")
    assert response.status_code == 503
    data = response.json()
    assert "not yet trained or loaded" in data["detail"]



def test_get_alerts_schema():
    """Verify alerts endpoint returns valid alerts conforming to frontend contract."""
    response = client.get("/api/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert isinstance(alerts, list)
    assert len(alerts) > 0

    first = alerts[0]
    expected_fields = ["id", "transactionId", "riskScore", "reason", "nextStep", "status"]
    for field in expected_fields:
        assert field in first
    assert first["status"] in ["Needs review", "In review", "Resolved"]


def test_get_metrics_schema():
    """Verify metrics endpoint returns required KPI fields conforming to lib/api.ts."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert "transactionsProcessed" in metrics
    assert "highRiskTransactions" in metrics
    assert "alertsGenerated" in metrics
    assert "averageLatencyMs" in metrics
    assert metrics["transactionsProcessed"] >= 0
    assert metrics["averageLatencyMs"] >= 0.0


def test_get_model_performance_schema():
    """Verify model performance endpoint returns authentic evaluation metrics."""
    response = client.get("/api/model/performance")
    assert response.status_code == 200
    perf = response.json()
    assert perf["status"] == "ready"
    assert perf["modelVersion"] == "1.0.0"
    assert perf["precision"] is not None
    assert perf["recall"] is not None
    assert perf["f1Score"] is not None
    assert perf["falsePositiveRate"] is not None
    assert perf["prAuc"] is not None
    assert "confusionMatrix" in perf
    assert "synthetic" in perf["datasetDisclosures"].lower()



def test_get_audit_trail_schema():
    """Verify audit records endpoint returns valid audit entries."""
    response = client.get("/api/audit")
    assert response.status_code == 200
    audit_logs = response.json()
    assert isinstance(audit_logs, list)
    assert len(audit_logs) > 0
    assert "id" in audit_logs[0]
    assert "action" in audit_logs[0]


def test_update_alert_status_success():
    """Verify updating alert status succeeds and reflects in alert retrieval."""
    alerts = client.get("/api/alerts").json()
    assert len(alerts) > 0
    alert_id = alerts[0]["id"]

    # Transition to 'In review'
    patch_res = client.patch(f"/api/alerts/{alert_id}", json={"status": "In review"})
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "In review"

    # Transition to 'Resolved'
    resolve_res = client.patch(f"/api/alerts/{alert_id}", json={"status": "Resolved"})
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "Resolved"


def test_update_alert_status_not_found():
    """Verify updating an invalid alert returns 404."""
    response = client.patch("/api/alerts/ALT-NONEXISTENT-9999", json={"status": "In review"})
    assert response.status_code == 404


def test_get_engine_config_schema():
    """Verify GET /api/engine/config returns active thresholds and policy rules."""
    response = client.get("/api/engine/config")
    assert response.status_code == 200
    cfg = response.json()
    assert "high_risk_threshold" in cfg
    assert "medium_risk_threshold" in cfg
    assert cfg["high_risk_threshold"] == 0.450
    assert cfg["medium_risk_threshold"] == 0.270
    assert cfg["action_high"] == "Hold for review"
    assert cfg["action_medium"] == "Step-up authentication"
    assert cfg["action_low"] == "Allow"
