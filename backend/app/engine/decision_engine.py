"""
Decision Engine for SentinelZ AI.
Provides evidence-based risk scoring, policy recommendations, boundary threshold classification,
and workflow review state tracking.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas import RiskLevel, ReviewStatus
from app.engine.config import DecisionEngineConfig, engine_config


class DecisionResult(BaseModel):
    """Encapsulates the comprehensive output of the decision engine."""
    riskScore: int = Field(..., ge=0, le=100, description="Normalized 0-100 display score")
    riskLevel: RiskLevel = Field(..., description="Categorized risk: low, medium, or high")
    modelProbability: float = Field(..., ge=0.0, le=1.0, description="Raw model estimated probability")
    recommendedAction: str = Field(..., description="Automated policy recommendation")
    indicators: List[str] = Field(default_factory=list, description="Evidence-based risk signals from observable features")
    reviewStatus: Optional[ReviewStatus] = Field(default=None, description="Triage workflow review status")
    syntheticDisclosure: str = Field(
        default="Synthetic demonstration benchmark. Decision guidance is advisory and not a final fraud determination.",
        description="Mandatory scientific transparency disclosure"
    )


class DecisionEngine:
    """
    Translates model probabilities and observable financial features into actionable risk intelligence.
    
    CRITICAL ARCHITECTURAL DISTINCTIONS:
    1. modelProbability: The mathematical posterior from the ML model [0.0, 1.0].
    2. riskScore: A normalized 0-100 integer display representation. It is NOT a calibrated probability.
    3. indicators: Observable rule-based risk signals present in transaction inputs. They are NOT internal
       SHAP attributions or proofs of fraud.
    4. recommendedAction: Automated policy guidance (Allow, Step-up authentication, Hold for review).
    5. reviewStatus: Human workflow lifecycle state (Needs review, In review, Resolved). A transaction
       is NEVER automatically marked 'Resolved' by an automated algorithm.
    """

    def __init__(self, config: Optional[DecisionEngineConfig] = None):
        self.config = config or engine_config

    def validate_probability(self, probability: float) -> float:
        """Validates that probability is a valid float strictly within [0.0, 1.0]."""
        if not isinstance(probability, (int, float)) or isinstance(probability, bool):
            raise TypeError(f"Probability must be a numeric float, got {type(probability).__name__}")
        if probability < 0.0 or probability > 1.0:
            raise ValueError(f"Probability must be bounded within [0.0, 1.0], got {probability}")
        return float(probability)

    def calculate_display_score(self, probability: float) -> int:
        """
        Scales probability [0.0, 1.0] to an integer display score [0, 100].
        Note: Clearly documented as a scaled display score, not an empirically calibrated probability.
        """
        prob = self.validate_probability(probability)
        return int(min(100, max(0, round(prob * 100))))

    def determine_risk_level(self, probability: float, cfg: Optional[DecisionEngineConfig] = None) -> RiskLevel:
        """
        Applies exact, central boundary logic to assign risk levels:
        - prob >= high_threshold: HIGH
        - medium_threshold <= prob < high_threshold: MEDIUM
        - prob < medium_threshold: LOW
        """
        prob = self.validate_probability(probability)
        active_config = cfg or self.config

        if prob >= active_config.high_risk_threshold:
            return RiskLevel.HIGH
        elif prob >= active_config.medium_risk_threshold:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def determine_recommended_action(self, risk_level: RiskLevel, cfg: Optional[DecisionEngineConfig] = None) -> str:
        """Maps risk level to policy-based recommendation."""
        active_config = cfg or self.config
        if risk_level == RiskLevel.HIGH:
            return active_config.action_high
        elif risk_level == RiskLevel.MEDIUM:
            return active_config.action_medium
        else:
            return active_config.action_low

    def determine_workflow_status(self, risk_level: RiskLevel) -> Optional[ReviewStatus]:
        """
        Assigns initial analyst review workflow state.
        High/Medium transactions require review (Needs review).
        Low risk transactions do not enter review queues by default (None).
        RULE: An automated algorithm NEVER marks a transaction 'Resolved'.
        """
        if risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
            return ReviewStatus.NEEDS_REVIEW
        return None

    def derive_indicators(self, features: Dict[str, Any], cfg: Optional[DecisionEngineConfig] = None) -> List[str]:
        """
        Evaluates observable transaction features against deterministic rules.
        CRITICAL: Only produces an indicator when the relevant input is present and non-null.
        """
        active_config = cfg or self.config
        indicators: List[str] = []

        # 1. Baseline Deviation
        ratio = features.get("amount_to_baseline_ratio")
        if ratio is None and "amount" in features and "customer_baseline" in features:
            amt = features.get("amount")
            base = features.get("customer_baseline")
            if amt is not None and base is not None and base > 0:
                ratio = amt / base

        if ratio is not None:
            if ratio >= active_config.amount_anomaly_multiplier:
                indicators.append(f"Amount anomaly ({ratio:.1f}x customer baseline)")
            elif ratio >= active_config.amount_elevated_multiplier:
                indicators.append(f"Elevated spend ({ratio:.1f}x customer baseline)")

        # 2. Transaction Velocity
        velocity = features.get("recent_transaction_count")
        if velocity is not None:
            if velocity >= active_config.velocity_burst_tx_per_hour:
                indicators.append(f"Velocity burst ({velocity} tx/hr)")
            elif velocity >= active_config.velocity_elevated_tx_per_hour:
                indicators.append(f"Unusual frequency ({velocity} tx/hr)")

        # 3. Transaction Cadence / Rapidity
        cadence = features.get("time_since_previous_seconds")
        if cadence is not None and cadence < active_config.rapid_cadence_seconds:
            indicators.append("Rapid succession (< 1m cadence)")

        # 4. Cross-Border Indicator
        is_foreign = features.get("is_foreign_country")
        if is_foreign is not None and is_foreign == 1:
            indicators.append("Cross-border origin")

        # 5. Device Risk Score
        dev_risk = features.get("device_risk_score")
        if dev_risk is not None and dev_risk >= active_config.device_risk_threshold:
            indicators.append("Unrecognized device profile")

        # 6. High-Value Channel Transfer
        channel = features.get("channel")
        amount = features.get("amount")
        if channel in ["Wire", "ACH"] and amount is not None and amount >= active_config.high_value_channel_amount:
            indicators.append(f"High-value {channel} transfer")

        # 7. High-Risk Merchant Category
        merchant = features.get("merchant_category")
        if merchant in active_config.high_risk_merchants:
            indicators.append(f"High-risk merchant ({merchant})")

        if not indicators:
            indicators.append("Normal activity pattern")

        return indicators

    def evaluate(
        self,
        model_probability: float,
        features: Dict[str, Any],
        custom_config: Optional[DecisionEngineConfig] = None,
    ) -> DecisionResult:
        """
        Executes end-to-end decision evaluation for a transaction given model probability and observable features.
        """
        prob = self.validate_probability(model_probability)
        cfg = custom_config or self.config

        risk_score = self.calculate_display_score(prob)
        risk_level = self.determine_risk_level(prob, cfg)
        recommended_action = self.determine_recommended_action(risk_level, cfg)
        review_status = self.determine_workflow_status(risk_level)
        indicators = self.derive_indicators(features, cfg)

        return DecisionResult(
            riskScore=risk_score,
            riskLevel=risk_level,
            modelProbability=round(prob, 4),
            recommendedAction=recommended_action,
            indicators=indicators,
            reviewStatus=review_status,
        )


# Global singleton instance
decision_engine = DecisionEngine()
