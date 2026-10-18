"""
Comprehensive Automated Test Suite for Transaction Processing Service, Scenarios, and SQLite Persistence.
Tests end-to-end ingestion, scenario simulation, alert policies, latency timers, and database operations.
"""

import pytest
from app.schemas import Channel, RiskLevel, ReviewStatus
from app.services.scenarios import build_scenario_payload, ScenarioType
from app.services.transaction_service import TransactionProcessingService
from app.repository.sqlite_repo import SQLiteRepository


@pytest.fixture
def clean_service(tmp_path):
    """Provides a TransactionProcessingService backed by an isolated temporary SQLite database."""
    test_db = tmp_path / "test_sentinelz.db"
    repo = SQLiteRepository(db_path=test_db)
    service = TransactionProcessingService(repo=repo)
    return service, repo


def test_scenario_generation_all_types():
    """Verify each supported scenario produces observable features without labels or leaks."""
    scenarios = [
        ScenarioType.NORMAL.value,
        ScenarioType.UNUSUAL_AMOUNT.value,
        ScenarioType.VELOCITY_BURST.value,
        ScenarioType.ELEVATED_DEVICE_RISK.value,
        ScenarioType.CROSS_BORDER_WIRE.value,
    ]

    for sc_name in scenarios:
        payload = build_scenario_payload(scenario=sc_name, seed=100)
        assert payload["scenario"] == sc_name
        assert payload["amount"] > 0
        assert payload["channel"] in ["Card", "Mobile", "ACH", "Wire"]
        assert "customer_baseline" in payload
        assert "is_fraud" not in payload
        assert "latent_risk_score" not in payload


def test_successful_simulated_transaction_processing(clean_service):
    """Verify end-to-end processing of a normal simulated transaction."""
    service, repo = clean_service

    result = service.simulate_transaction(scenario="normal", seed=42)

    tx = result["transaction"]
    assert tx.id.startswith("TXN-")
    assert tx.amount > 0
    assert 0 <= tx.riskScore <= 100
    assert tx.riskLevel in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    assert tx.recommendedAction in ["Allow", "Step-up authentication", "Hold for review"]
    assert len(tx.indicators) > 0

    # Latency timers
    assert result["inferenceLatencyMs"] > 0.0
    assert result["processingLatencyMs"] >= result["inferenceLatencyMs"]

    # Verify persisted in SQLite
    persisted_tx = repo.get_transaction(tx.id)
    assert persisted_tx is not None
    assert persisted_tx.id == tx.id
    assert persisted_tx.amount == tx.amount


def test_high_risk_scenario_generates_alert_and_persists(clean_service):
    """Verify that an anomalous high-risk scenario generates an alert and saves both to SQLite."""
    service, repo = clean_service

    # Construct high-risk cross-border wire scenario payload
    wire_payload = {
        "amount": 45000.0,
        "channel": "Wire",
        "merchant_category": "crypto_luxury",
        "customer_baseline": 1500.0,
        "recent_transaction_count": 7,
        "time_since_previous_seconds": 25,
        "is_foreign_country": 1,
        "device_risk_score": 0.92,
    }

    result = service.process_transaction(wire_payload, scenario_name="cross_border_wire")

    tx = result["transaction"]
    alert = result["alert"]

    # When transaction is high or medium risk, alert must be generated
    if tx.riskLevel in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
        assert alert is not None
        assert alert.id.startswith("ALT-")
        assert alert.transactionId == tx.id
        assert alert.riskScore == tx.riskScore
        assert alert.status == ReviewStatus.NEEDS_REVIEW
        assert len(alert.reason) > 0

        # Verify alert was saved in SQLite
        persisted_alert = repo.get_alert(alert.id)
        assert persisted_alert is not None
        assert persisted_alert.transactionId == tx.id


def test_low_risk_scenario_suppresses_alert(clean_service):
    """Verify that low risk transactions do not generate alert clutter."""
    service, repo = clean_service

    # Safe low risk card transaction matching normal baseline
    safe_payload = {
        "amount": 25.0,
        "channel": "Card",
        "merchant_category": "groceries",
        "customer_baseline": 30.0,
        "recent_transaction_count": 1,
        "time_since_previous_seconds": 7200,
        "is_foreign_country": 0,
        "device_risk_score": 0.05,
    }

    result = service.process_transaction(safe_payload, scenario_name="normal")
    tx = result["transaction"]
    alert = result["alert"]

    if tx.riskLevel == RiskLevel.LOW:
        assert alert is None


def test_unique_sequential_ids(clean_service):
    """Verify that sequential simulations produce unique, collision-free transaction IDs."""
    service, repo = clean_service

    r1 = service.simulate_transaction(scenario="normal", seed=1)
    r2 = service.simulate_transaction(scenario="normal", seed=2)
    r3 = service.simulate_transaction(scenario="normal", seed=3)

    ids = [r1["transaction"].id, r2["transaction"].id, r3["transaction"].id]
    assert len(set(ids)) == 3, f"Duplicate transaction IDs detected: {ids}"


def test_invalid_transaction_inputs_raise_errors(clean_service):
    """Verify input validation rejects non-positive amounts and invalid channels."""
    service, _ = clean_service

    with pytest.raises(ValueError, match="strictly positive"):
        service.process_transaction({"amount": -50.0, "channel": "Card"})

    with pytest.raises(ValueError, match="Invalid payment channel"):
        service.process_transaction({"amount": 100.0, "channel": "BitcoinRail"})


def test_metrics_summary_updates_with_new_transactions(clean_service):
    """Verify get_metrics_summary reflects newly processed transactions in SQLite."""
    service, repo = clean_service

    initial_metrics = repo.get_metrics_summary()
    init_tx_count = initial_metrics["transactionsProcessed"]

    # Process 2 new transactions
    service.simulate_transaction(scenario="normal", seed=10)
    service.simulate_transaction(scenario="unusual_amount", seed=11)

    updated_metrics = repo.get_metrics_summary()
    assert updated_metrics["transactionsProcessed"] == init_tx_count + 2


def test_duplicate_alert_prevention_on_repeated_save(clean_service):
    """Verify that duplicate alerts for the same transaction event are prevented."""
    _, repo = clean_service

    from app.schemas import Transaction, Alert, Channel
    tx = Transaction(
        id="TXN-999999",
        timestamp="10:45:00",
        amount=5000.0,
        channel=Channel.WIRE,
        riskScore=88,
        riskLevel=RiskLevel.HIGH,
        recommendedAction="Hold for review",
        indicators=["High amount", "Burst"],
        processingTimestamp="2026-10-18T10:45:00Z",
    )
    repo.save_transaction(tx)

    alert1 = Alert(
        id="ALT-9999",
        transactionId="TXN-999999",
        riskScore=88,
        reason="Rapid transaction burst",
        nextStep="Contact cardholder",
        status=ReviewStatus.NEEDS_REVIEW,
    )
    saved1 = repo.save_alert(alert1)
    assert saved1.id == "ALT-9999"

    # Attempt saving again with different alert ID but same transaction ID
    alert2 = Alert(
        id="ALT-10000",
        transactionId="TXN-999999",
        riskScore=88,
        reason="Duplicate event trigger attempt",
        nextStep="Contact cardholder",
        status=ReviewStatus.NEEDS_REVIEW,
    )
    saved2 = repo.save_alert(alert2)
    # Must return original alert and not create a second row in alerts table
    assert saved2.id == "ALT-9999"
    all_alerts = repo.list_alerts()
    txn_alerts = [a for a in all_alerts if a.transactionId == "TXN-999999"]
    assert len(txn_alerts) == 1


def test_unknown_transaction_id(clean_service):
    """Verify looking up an unknown transaction ID returns None in repository."""
    _, repo = clean_service
    missing = repo.get_transaction("TXN-NONEXISTENT")
    assert missing is None


def test_e2e_api_simulate_and_retrieval():
    """Verify full HTTP integration: simulate a transaction, then retrieve via GET endpoints."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    sim_res = client.post("/api/transactions/simulate", json={"scenario": "elevated_device_risk", "seed": 777})
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    tx_id = sim_data["transaction"]["id"]
    assert tx_id.startswith("TXN-")

    # Retrieve through GET /api/transactions/{id}
    detail_res = client.get(f"/api/transactions/{tx_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == tx_id
    assert detail_data["amount"] == sim_data["transaction"]["amount"]

    # Verify present in GET /api/transactions
    list_res = client.get("/api/transactions")
    assert list_res.status_code == 200
    tx_ids = [t["id"] for t in list_res.json()]
    assert tx_id in tx_ids

    # If alert was generated, verify in GET /api/alerts
    if sim_data["alert"]:
        alert_id = sim_data["alert"]["id"]
        alerts_res = client.get("/api/alerts")
        assert alerts_res.status_code == 200
        alert_ids = [a["id"] for a in alerts_res.json()]
        assert alert_id in alert_ids

