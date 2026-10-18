"""
Automated Unit Tests for Decision Engine, Threshold Boundaries, and Indicator Rules.
Verifies boundary accuracy, probability validation, evidence-based rule triggers,
and separation of automated recommendations from human workflow status.
"""

import pytest
from app.schemas import RiskLevel, ReviewStatus
from app.engine.config import DecisionEngineConfig
from app.engine.decision_engine import DecisionEngine, decision_engine


def test_probability_validation_boundaries():
    """Verify engine rejects probabilities outside [0.0, 1.0] and invalid types."""
    engine = DecisionEngine()

    # Valid bounds
    assert engine.validate_probability(0.0) == 0.0
    assert engine.validate_probability(1.0) == 1.0
    assert engine.validate_probability(0.45) == 0.45

    # Out of bounds
    with pytest.raises(ValueError, match=r"bounded within \[0.0, 1.0\]"):
        engine.validate_probability(-0.01)

    with pytest.raises(ValueError, match=r"bounded within \[0.0, 1.0\]"):
        engine.validate_probability(1.001)

    # Invalid types
    with pytest.raises(TypeError):
        engine.validate_probability("0.5")  # type: ignore

    with pytest.raises(TypeError):
        engine.validate_probability(True)  # type: ignore


def test_display_risk_score_calculation():
    """Verify display score maps cleanly to [0, 100] integer."""
    engine = DecisionEngine()
    assert engine.calculate_display_score(0.0) == 0
    assert engine.calculate_display_score(1.0) == 100
    assert engine.calculate_display_score(0.454) == 45
    assert engine.calculate_display_score(0.456) == 46


def test_exact_threshold_boundary_behavior():
    """
    Test exact boundary handling:
    Config: medium = 0.270, high = 0.450
    - prob < 0.270 -> LOW
    - prob == 0.270 -> MEDIUM
    - 0.270 < prob < 0.450 -> MEDIUM
    - prob == 0.450 -> HIGH
    - prob > 0.450 -> HIGH
    """
    cfg = DecisionEngineConfig(medium_risk_threshold=0.270, high_risk_threshold=0.450)
    engine = DecisionEngine(config=cfg)

    # Just below medium
    assert engine.determine_risk_level(0.269, cfg) == RiskLevel.LOW
    # Exactly at medium
    assert engine.determine_risk_level(0.270, cfg) == RiskLevel.MEDIUM
    # Just above medium
    assert engine.determine_risk_level(0.271, cfg) == RiskLevel.MEDIUM

    # Just below high
    assert engine.determine_risk_level(0.449, cfg) == RiskLevel.MEDIUM
    # Exactly at high
    assert engine.determine_risk_level(0.450, cfg) == RiskLevel.HIGH
    # Just above high
    assert engine.determine_risk_level(0.451, cfg) == RiskLevel.HIGH


def test_recommended_action_policy():
    """Verify policy recommendations align with risk categories."""
    engine = DecisionEngine()
    assert engine.determine_recommended_action(RiskLevel.HIGH) == "Hold for review"
    assert engine.determine_recommended_action(RiskLevel.MEDIUM) == "Step-up authentication"
    assert engine.determine_recommended_action(RiskLevel.LOW) == "Allow"


def test_review_status_separation():
    """
    Verify review status represents workflow, not predicted risk.
    CRITICAL RULE: The engine NEVER automatically assigns 'Resolved'.
    """
    engine = DecisionEngine()
    # High risk enters review queue
    assert engine.determine_workflow_status(RiskLevel.HIGH) == ReviewStatus.NEEDS_REVIEW
    # Medium risk enters review queue
    assert engine.determine_workflow_status(RiskLevel.MEDIUM) == ReviewStatus.NEEDS_REVIEW
    # Low risk does not require review
    assert engine.determine_workflow_status(RiskLevel.LOW) is None

    # Verify 'Resolved' is never produced
    for level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]:
        assert engine.determine_workflow_status(level) != ReviewStatus.RESOLVED


def test_indicator_generation_rules():
    """Verify indicators fire accurately when evidence conditions are met."""
    engine = DecisionEngine()

    # 1. Amount anomaly (>= 4x)
    indicators = engine.derive_indicators({"amount": 5000.0, "customer_baseline": 1000.0})
    assert any("Amount anomaly (5.0x" in ind for ind in indicators)

    # 2. Elevated spend (2x to 4x)
    indicators = engine.derive_indicators({"amount": 2500.0, "customer_baseline": 1000.0})
    assert any("Elevated spend (2.5x" in ind for ind in indicators)

    # 3. Velocity burst (>= 5)
    indicators = engine.derive_indicators({"recent_transaction_count": 6})
    assert any("Velocity burst (6 tx/hr)" in ind for ind in indicators)

    # 4. Rapid cadence (< 60s)
    indicators = engine.derive_indicators({"time_since_previous_seconds": 25})
    assert any("Rapid succession" in ind for ind in indicators)

    # 5. Cross-border origin
    indicators = engine.derive_indicators({"is_foreign_country": 1})
    assert any("Cross-border origin" in ind for ind in indicators)

    # 6. Unrecognized device
    indicators = engine.derive_indicators({"device_risk_score": 0.85})
    assert any("Unrecognized device profile" in ind for ind in indicators)

    # 7. High-value Wire
    indicators = engine.derive_indicators({"channel": "Wire", "amount": 25000.0})
    assert any("High-value Wire transfer" in ind for ind in indicators)

    # 8. High-risk merchant
    indicators = engine.derive_indicators({"merchant_category": "crypto_luxury"})
    assert any("High-risk merchant (crypto_luxury)" in ind for ind in indicators)


def test_no_indicators_fabricated_when_fields_missing():
    """Verify that absent features NEVER trigger false evidence indicators."""
    engine = DecisionEngine()

    # Minimal feature set: only normal card transaction, no foreign flag, no device score
    empty_features = {"amount": 50.0, "customer_baseline": 50.0, "channel": "Card"}
    indicators = engine.derive_indicators(empty_features)

    # None of the high-risk indicators should be triggered
    joined = " ".join(indicators).lower()
    assert "cross-border" not in joined
    assert "unrecognized device" not in joined
    assert "velocity" not in joined
    assert "cadence" not in joined
    assert "anomaly" not in joined
    assert "Normal activity pattern" in indicators


def test_decision_engine_config_validation():
    """Verify configuration rejects invalid threshold ordering."""
    with pytest.raises(ValueError, match="strictly less than"):
        # medium threshold cannot be >= high threshold
        DecisionEngineConfig(medium_risk_threshold=0.50, high_risk_threshold=0.40)

    with pytest.raises(ValueError, match="strictly less than"):
        # medium threshold cannot equal high threshold
        DecisionEngineConfig(medium_risk_threshold=0.45, high_risk_threshold=0.45)


def test_end_to_end_evaluate_decision_result():
    """Verify end-to-end evaluation output object."""
    engine = DecisionEngine()
    features = {
        "amount": 12000.0,
        "customer_baseline": 1500.0,
        "channel": "Wire",
        "recent_transaction_count": 6,
        "time_since_previous_seconds": 40,
        "is_foreign_country": 1,
        "device_risk_score": 0.88,
    }

    result = engine.evaluate(model_probability=0.72, features=features)

    assert result.riskScore == 72
    assert result.riskLevel == RiskLevel.HIGH
    assert result.modelProbability == 0.72
    assert result.recommendedAction == "Hold for review"
    assert result.reviewStatus == ReviewStatus.NEEDS_REVIEW
    assert len(result.indicators) >= 4
    assert "synthetic" in result.syntheticDisclosure.lower()
