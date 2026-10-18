"""
Centralized Configuration for Decision Engine, Risk Thresholds, and Policy Rules.
Maintains a single source of truth for risk boundary logic and indicator trigger thresholds.
"""

from typing import List, Dict
from pydantic import BaseModel, Field, model_validator


class DecisionEngineConfig(BaseModel):
    """
    Centralized configuration for risk scoring, boundary thresholds, and indicator rules.
    Easily adjustable during demonstrations or production policy tuning.
    """

    # Boundary thresholds for mapping raw model probability (0.0 to 1.0) to risk levels
    # High threshold matches the validation-tuned threshold from model training (0.450)
    high_risk_threshold: float = Field(
        default=0.450,
        ge=0.01,
        le=0.99,
        description="Probability threshold for HIGH risk (inclusive: prob >= high_risk_threshold)"
    )
    medium_risk_threshold: float = Field(
        default=0.270,
        ge=0.01,
        le=0.99,
        description="Probability threshold for MEDIUM risk (inclusive: prob >= medium_risk_threshold)"
    )

    # Indicator Trigger Rules (Evidence-Based Observations)
    amount_anomaly_multiplier: float = Field(default=4.0, gt=1.0)
    amount_elevated_multiplier: float = Field(default=2.0, gt=1.0)
    velocity_burst_tx_per_hour: int = Field(default=5, ge=1)
    velocity_elevated_tx_per_hour: int = Field(default=3, ge=1)
    rapid_cadence_seconds: int = Field(default=60, ge=1)
    device_risk_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    high_value_channel_amount: float = Field(default=10000.0, gt=0.0)
    high_risk_merchants: List[str] = Field(
        default_factory=lambda: ["crypto_luxury", "digital_transfer"]
    )

    # Recommended Actions
    action_high: str = "Hold for review"
    action_medium: str = "Step-up authentication"
    action_low: str = "Allow"

    @model_validator(mode="after")
    def validate_threshold_ordering(self) -> "DecisionEngineConfig":
        """Ensures medium threshold is strictly less than high threshold."""
        if self.medium_risk_threshold >= self.high_risk_threshold:
            raise ValueError(
                f"medium_risk_threshold ({self.medium_risk_threshold}) must be strictly less than "
                f"high_risk_threshold ({self.high_risk_threshold})"
            )
        return self


# Global singleton configuration instance
engine_config = DecisionEngineConfig()
