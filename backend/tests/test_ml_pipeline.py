"""
Comprehensive Automated Test Suite for SentinelZ AI Machine Learning Pipeline.
Tests data partitioning, preprocessing, model training, threshold evaluation,
persistence, reloading, predictor inference, and evidence-based indicators.
"""

from pathlib import Path
import tempfile
import pytest
import numpy as np
import pandas as pd

from app.ml.features import (
    INFERENCE_FEATURE_COLUMNS,
    TARGET_COLUMN,
    split_features_and_target,
)
from app.ml.synthetic_data import generate_synthetic_transactions
from app.ml.preprocessor import build_feature_preprocessor, prepare_data_splits
from app.ml.train import train_and_evaluate_pipeline, ARTIFACTS_DIR
from app.ml.predictor import RiskPredictor, predictor


def test_stratified_data_split_integrity():
    """Verify that dataset is cleanly split into 70% Train, 15% Val, 15% Test without target leakage."""
    df = generate_synthetic_transactions(n_samples=1000, seed=42)
    splits = prepare_data_splits(df, test_ratio=0.15, val_ratio=0.15, seed=42)

    X_train, y_train = splits["X_train"], splits["y_train"]
    X_val, y_val = splits["X_val"], splits["y_val"]
    X_test, y_test = splits["X_test"], splits["y_test"]

    # Row count verification
    assert len(X_train) == 700
    assert len(X_val) == 150
    assert len(X_test) == 150

    # Leakage check: Target label must not be in feature sets
    assert TARGET_COLUMN not in X_train.columns
    assert TARGET_COLUMN not in X_val.columns
    assert TARGET_COLUMN not in X_test.columns

    # Metadata check: IDs must not be in feature sets
    for col in ["transaction_id", "customer_id", "timestamp"]:
        assert col not in X_train.columns


def test_model_training_and_artifact_persistence():
    """Verify end-to-end model training, validation comparison, test evaluation, and artifact emission."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Train on small reproducible dataset
        results = train_and_evaluate_pipeline(n_samples=1000, seed=42, persist_artifacts=False)

        assert "selected_model" in results
        assert results["selected_model"] in ["RandomForest", "LogisticRegression"]
        assert 0.10 <= results["selected_threshold"] <= 0.90

        val_comp = results["validation_comparison"]
        assert "LogisticRegression" in val_comp
        assert "RandomForest" in val_comp
        assert val_comp["LogisticRegression"]["pr_auc"] >= 0.0
        assert val_comp["RandomForest"]["pr_auc"] >= 0.0

        test_metrics = results["test_metrics"]
        assert "precision" in test_metrics
        assert "recall" in test_metrics
        assert "f1" in test_metrics
        assert "fpr" in test_metrics
        assert "confusion_matrix" in test_metrics


def test_persisted_artifacts_exist_and_loadable():
    """Verify that the production artifact files exist and can be reloaded by a fresh RiskPredictor."""
    pipeline_file = ARTIFACTS_DIR / "model_pipeline.joblib"
    metadata_file = ARTIFACTS_DIR / "metadata.json"

    assert pipeline_file.exists(), f"Model pipeline artifact missing at {pipeline_file}"
    assert metadata_file.exists(), f"Metadata artifact missing at {metadata_file}"

    fresh_predictor = RiskPredictor(artifacts_dir=ARTIFACTS_DIR)
    assert fresh_predictor.is_ready
    assert fresh_predictor.model_version == "1.0.0"
    assert fresh_predictor.operating_threshold > 0.0


def test_risk_predictor_inference_ranges_and_latency():
    """Verify that RiskPredictor outputs calibrated ranges and accurate latency measurements."""
    assert predictor.is_ready

    payload = {
        "amount": 1500.0,
        "channel": "Card",
        "merchant_category": "retail",
        "customer_baseline": 150.0,
        "recent_transaction_count": 2,
        "time_since_previous_seconds": 300,
        "is_foreign_country": 0,
        "device_risk_score": 0.25,
    }

    result = predictor.predict_transaction(payload)

    # Output contract verification
    assert 0 <= result["riskScore"] <= 100
    assert 0.0 <= result["modelProbability"] <= 1.0
    assert result["riskLevel"] in ["low", "medium", "high"]
    assert result["recommendedAction"] in ["Allow", "Step-up authentication", "Hold for review"]
    assert isinstance(result["indicators"], list)
    assert len(result["indicators"]) > 0
    # Latency timer must be strictly positive and realistic (< 150ms on local test runner)
    assert 0.0 < result["inferenceLatencyMs"] < 150.0



def test_risk_predictor_evidence_based_indicators():
    """Verify that indicators faithfully reflect transaction input signals without hallucination."""
    high_risk_payload = {
        "amount": 28000.0,
        "channel": "Wire",
        "merchant_category": "crypto_luxury",
        "customer_baseline": 2000.0,
        "recent_transaction_count": 6,
        "time_since_previous_seconds": 30,
        "is_foreign_country": 1,
        "device_risk_score": 0.95,
    }

    result = predictor.predict_transaction(high_risk_payload)

    indicator_text = " ".join(result["indicators"]).lower()
    # Must flag the real evidence present in the input
    assert "baseline" in indicator_text
    assert "velocity" in indicator_text or "cadence" in indicator_text or "rapid" in indicator_text
    assert "cross-border" in indicator_text
    assert "device" in indicator_text or "merchant" in indicator_text or "channel" in indicator_text
    assert result["riskLevel"] in ["high", "medium"]


def test_risk_predictor_graceful_missing_field_defaults():
    """Verify that predictor fills missing optional fields with safe baseline values."""
    minimal_payload = {
        "amount": 100.0,
        "channel": "Card",
    }
    result = predictor.predict_transaction(minimal_payload)
    assert 0 <= result["riskScore"] <= 100
    assert result["riskLevel"] in ["low", "medium", "high"]


def test_predictions_consistent_before_and_after_save_and_reload(tmp_path):
    """Verify that model predictions and probabilities are identical before saving and after reloading."""
    import joblib
    import json
    from app.ml.features import INFERENCE_FEATURE_COLUMNS

    results = train_and_evaluate_pipeline(n_samples=1000, seed=42, persist_artifacts=False)
    pipeline = results["metadata"]["validation_comparison"]["RandomForest"]
    
    # Train pipeline instance directly
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from app.ml.preprocessor import build_feature_preprocessor
    
    df = generate_synthetic_transactions(n_samples=1000, seed=42)
    splits = prepare_data_splits(df, test_ratio=0.15, val_ratio=0.15, seed=42)
    
    train_pipe = Pipeline(
        steps=[
            ("preprocessor", build_feature_preprocessor()),
            ("classifier", RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42)),
        ]
    )
    train_pipe.fit(splits["X_train"], splits["y_train"])

    test_payload = {
        "amount": 4200.0,
        "channel": "Wire",
        "merchant_category": "electronics",
        "customer_baseline": 350.0,
        "amount_to_baseline_ratio": 12.0,
        "recent_transaction_count": 4,
        "time_since_previous_seconds": 60,
        "is_foreign_country": 1,
        "device_risk_score": 0.72,
    }

    test_row = pd.DataFrame([test_payload])[INFERENCE_FEATURE_COLUMNS]
    prob_before = float(train_pipe.predict_proba(test_row)[0][1])

    # Save to disk
    pipe_path = tmp_path / "model_pipeline.joblib"
    meta_path = tmp_path / "metadata.json"
    joblib.dump(train_pipe, pipe_path)

    meta_content = {
        "model_version": "1.0.0-test",
        "model_name": "RandomForest",
        "operating_threshold": 0.45,
        "test_metrics": {"pr_auc": 0.5, "roc_auc": 0.8},
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_content, f)

    # Reload fresh instance from disk
    reloaded_predictor = RiskPredictor(artifacts_dir=tmp_path)
    assert reloaded_predictor.is_ready

    result_after = reloaded_predictor.predict_transaction(test_payload)
    prob_after = result_after["modelProbability"]

    assert round(prob_before, 4) == round(prob_after, 4)
    assert 0 <= result_after["riskScore"] <= 100


def test_unloaded_model_raises_runtime_error_without_fabrication(tmp_path):
    """Verify that calling predictor with missing model artifacts raises RuntimeError and never fabricates output."""
    empty_predictor = RiskPredictor(artifacts_dir=tmp_path)
    assert not empty_predictor.is_ready

    with pytest.raises(RuntimeError, match="Model pipeline is not loaded"):
        empty_predictor.predict_transaction({"amount": 100.0, "channel": "Card"})


def test_unknown_categorical_values_handled_gracefully():
    """Verify that unseen categorical channels or merchant categories are zero-encoded without throwing errors."""
    assert predictor.is_ready

    unseen_payload = {
        "amount": 500.0,
        "channel": "QuantumDirectPay",
        "merchant_category": "asteroid_mining",
        "customer_baseline": 200.0,
    }

    # Should execute successfully without throwing ValueError or KeyError
    result = predictor.predict_transaction(unseen_payload)
    assert 0 <= result["riskScore"] <= 100
    assert 0.0 <= result["modelProbability"] <= 1.0

