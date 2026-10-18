"""
Model prediction and evaluation endpoints for SentinelZ AI.
Connects directly to the trained RiskPredictor with authentic performance benchmarks.
"""

from fastapi import APIRouter, HTTPException, status
from app.ml.predictor import predictor
from app.engine.config import engine_config
from app.schemas import PredictionRequest, PredictionResponse, ModelPerformance, EngineConfigResponse

router = APIRouter(tags=["Model & Predictions"])


@router.get("/engine/config", response_model=EngineConfigResponse)
def get_engine_config() -> EngineConfigResponse:
    """
    Returns active decision engine boundary thresholds, action mappings,
    and observable indicator trigger parameters.
    """
    return EngineConfigResponse(
        high_risk_threshold=engine_config.high_risk_threshold,
        medium_risk_threshold=engine_config.medium_risk_threshold,
        amount_anomaly_multiplier=engine_config.amount_anomaly_multiplier,
        amount_elevated_multiplier=engine_config.amount_elevated_multiplier,
        velocity_burst_tx_per_hour=engine_config.velocity_burst_tx_per_hour,
        velocity_elevated_tx_per_hour=engine_config.velocity_elevated_tx_per_hour,
        rapid_cadence_seconds=engine_config.rapid_cadence_seconds,
        device_risk_threshold=engine_config.device_risk_threshold,
        high_value_channel_amount=engine_config.high_value_channel_amount,
        high_risk_merchants=engine_config.high_risk_merchants,
        action_high=engine_config.action_high,
        action_medium=engine_config.action_medium,
        action_low=engine_config.action_low,
    )


@router.post("/predict", response_model=PredictionResponse)
def predict_transaction(payload: PredictionRequest) -> PredictionResponse:
    """
    Evaluates a transaction for fraud risk using the trained machine-learning model.
    Returns estimated probability, display risk score, action recommendation, and indicators.
    """
    if not predictor.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine-learning model is not yet trained or loaded. Run model training pipeline first."
        )

    try:
        result = predictor.predict_transaction(payload.model_dump())
        return PredictionResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failure: {str(e)}"
        )


@router.get("/model/performance", response_model=ModelPerformance)
def get_model_performance() -> ModelPerformance:
    """
    Returns authentic model performance benchmarks measured on the held-out test set.
    """
    if not predictor.is_ready:
        return ModelPerformance(
            status="pending_evaluation",
            modelVersion="Pending evaluation",
            precision=None,
            recall=None,
            f1Score=None,
            falsePositiveRate=None,
            prAuc=None,
            confusionMatrix=None,
            datasetDisclosures=(
                "Model training pipeline is scheduled for Stage 4. Metrics will be calculated "
                "on held-out test splits using synthetic banking activity data. "
                "Synthetic data benchmarks must not be represented as verified real-world bank production metrics."
            ),
        )

    meta = predictor.metadata
    test_metrics = meta.get("test_metrics", {})
    return ModelPerformance(
        status="ready",
        modelVersion=meta.get("model_version", "1.0.0"),
        precision=test_metrics.get("precision"),
        recall=test_metrics.get("recall"),
        f1Score=test_metrics.get("f1"),
        falsePositiveRate=test_metrics.get("fpr"),
        prAuc=test_metrics.get("pr_auc"),
        rocAuc=test_metrics.get("roc_auc"),
        confusionMatrix=test_metrics.get("confusion_matrix"),
        datasetDisclosures=meta.get(
            "synthetic_data_disclosure",
            "Demonstration benchmark derived from held-out synthetic test transactions."
        ),
    )

