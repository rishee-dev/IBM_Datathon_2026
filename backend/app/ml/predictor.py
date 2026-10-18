"""
Reusable RiskPredictor for SentinelZ AI.
Loads persisted model pipeline and metadata, validates feature schema, measures inference latency,
and delegates risk scoring and policy evaluation to the central DecisionEngine.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd

from app.ml.features import INFERENCE_FEATURE_COLUMNS
from app.engine.decision_engine import decision_engine, DecisionEngineConfig

logger = logging.getLogger("sentinelz.ml.predictor")
DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


class RiskPredictor:
    """
    Inference engine for real-time transaction risk scoring.
    Delegates policy decisions, threshold boundary mapping, and indicators to DecisionEngine.
    """

    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS_DIR
        self.model_pipeline = None
        self.metadata: Dict[str, Any] = {}
        self.operating_threshold: float = 0.450
        self.model_version: str = "unavailable"
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Loads serialized model pipeline and metadata from artifacts directory."""
        pipeline_path = self.artifacts_dir / "model_pipeline.joblib"
        metadata_path = self.artifacts_dir / "metadata.json"

        if not pipeline_path.exists() or not metadata_path.exists():
            logger.warning("Model artifacts not found in %s. Predictor is uninitialized.", self.artifacts_dir)
            return

        try:
            self.model_pipeline = joblib.load(pipeline_path)
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

            self.operating_threshold = float(self.metadata.get("operating_threshold", 0.450))
            self.model_version = str(self.metadata.get("model_version", "1.0.0"))

            # Synchronize decision engine thresholds with model metadata
            decision_engine.config.high_risk_threshold = self.operating_threshold
            decision_engine.config.medium_risk_threshold = round(self.operating_threshold * 0.60, 3)

            logger.info(
                "RiskPredictor loaded model '%s' (v%s, threshold=%.3f)",
                self.metadata.get("model_name", "Unknown"),
                self.model_version,
                self.operating_threshold,
            )
        except Exception as e:
            logger.error("Failed to load model artifacts from %s: %s", self.artifacts_dir, str(e))
            self.model_pipeline = None
            self.metadata = {}

    @property
    def is_ready(self) -> bool:
        """Returns True if model pipeline and metadata are successfully loaded."""
        return self.model_pipeline is not None and bool(self.metadata)

    def extract_indicators(self, features: Dict[str, Any]) -> List[str]:
        """Backward-compatible proxy delegating indicator derivation to DecisionEngine."""
        return decision_engine.derive_indicators(features)

    def predict_transaction(self, raw_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs feature preparation, model inference, and delegates decision logic to DecisionEngine.

        Parameters:
        - raw_features: Dict matching PredictionRequest fields.

        Returns:
        - Dict with: riskScore, riskLevel, modelProbability, recommendedAction,
          indicators, reviewStatus, inferenceLatencyMs, modelVersion, syntheticDisclosure.
        """
        if not self.is_ready:
            raise RuntimeError("Model pipeline is not loaded. Train the model via app.ml.train first.")

        start_time = time.perf_counter()

        # Format input feature dictionary with safe defaults for missing optional features
        amount = float(raw_features.get("amount", 0.0))
        baseline = float(raw_features.get("customer_baseline") or amount)
        ratio = float(raw_features.get("amount_to_baseline_ratio") or (amount / max(baseline, 1.0)))

        row: Dict[str, Any] = {
            "amount": amount,
            "customer_baseline": baseline,
            "amount_to_baseline_ratio": ratio,
            "recent_transaction_count": int(raw_features.get("recent_transaction_count") or 1),
            "time_since_previous_seconds": int(raw_features.get("time_since_previous_seconds") or 3600),
            "device_risk_score": float(raw_features.get("device_risk_score") or 0.15),
            "channel": str(raw_features.get("channel", "Card")),
            "merchant_category": str(raw_features.get("merchant_category") or "retail"),
            "is_foreign_country": int(raw_features.get("is_foreign_country") or 0),
        }

        # Validate that all required inference columns are populated
        X_df = pd.DataFrame([row])[INFERENCE_FEATURE_COLUMNS]

        # Model inference: predict probabilities
        probabilities = self.model_pipeline.predict_proba(X_df)[0]
        prob_fraud = float(probabilities[1])

        # Precise inference latency measurement (excludes downstream network latency)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Delegate decision rules, risk boundaries, and indicators to DecisionEngine
        decision = decision_engine.evaluate(prob_fraud, row)

        return {
            "transactionId": raw_features.get("transactionId") or raw_features.get("id"),
            "riskScore": decision.riskScore,
            "riskLevel": decision.riskLevel,
            "modelProbability": decision.modelProbability,
            "recommendedAction": decision.recommendedAction,
            "indicators": decision.indicators,
            "reviewStatus": decision.reviewStatus,
            "inferenceLatencyMs": latency_ms,
            "modelVersion": self.model_version,
            "syntheticDisclosure": decision.syntheticDisclosure,
        }


# Global singleton instance for efficient in-memory inference across API requests
predictor = RiskPredictor()
