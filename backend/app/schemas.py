"""
Pydantic schemas matching frontend TypeScript contracts from lib/api.ts.
Field names and enum values strictly align with the Next.js client contracts.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStatus(str, Enum):
    NEEDS_REVIEW = "Needs review"
    IN_REVIEW = "In review"
    RESOLVED = "Resolved"


class Channel(str, Enum):
    WIRE = "Wire"
    CARD = "Card"
    ACH = "ACH"
    MOBILE = "Mobile"


class Transaction(BaseModel):
    id: str = Field(..., description="Unique transaction identifier, e.g. TXN-849201")
    timestamp: str = Field(..., description="Transaction initiation timestamp (e.g., '10:42:18.205')")
    amount: float = Field(..., ge=0.0, description="Transaction monetary amount")
    channel: Channel = Field(..., description="Payment channel: Wire, Card, ACH, or Mobile")
    riskScore: int = Field(..., ge=0, le=100, description="Risk score on normalized 0-100 scale")
    riskLevel: RiskLevel = Field(..., description="Categorized risk: low, medium, or high")
    recommendedAction: str = Field(..., description="Evidence-based policy recommendation")
    indicators: List[str] = Field(default_factory=list, description="List of triggered risk indicators")
    processingTimestamp: str = Field(..., description="Completion timestamp of processing")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "TXN-849201",
                "timestamp": "10:42:18.205",
                "amount": 24850.0,
                "channel": "Wire",
                "riskScore": 92,
                "riskLevel": "high",
                "recommendedAction": "Hold for review",
                "indicators": ["Velocity anomaly", "New beneficiary", "Geo mismatch"],
                "processingTimestamp": "10:42:18.221"
            }
        }
    }


class Metrics(BaseModel):
    transactionsProcessed: int = Field(..., ge=0, description="Total count of transactions processed")
    highRiskTransactions: int = Field(..., ge=0, description="Count of high-risk transactions detected")
    alertsGenerated: int = Field(..., ge=0, description="Count of actionable alerts created")
    averageLatencyMs: float = Field(..., ge=0.0, description="Average end-to-end processing latency in ms")
    volumeData: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional time-series points for volume chart"
    )
    latencyData: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional time-series points for latency chart"
    )


class Alert(BaseModel):
    id: str = Field(..., description="Unique alert identifier, e.g. ALT-2048")
    transactionId: str = Field(..., description="Associated transaction ID")
    riskScore: int = Field(..., ge=0, le=100, description="Risk score at alert creation")
    reason: str = Field(..., description="Primary reason for alert trigger")
    nextStep: str = Field(..., description="Recommended investigative action for analyst")
    status: ReviewStatus = Field(..., description="Alert lifecycle review status")


class PredictionRequest(BaseModel):
    amount: float = Field(..., gt=0.0, description="Transaction amount (must be positive)")
    channel: Channel = Field(..., description="Channel: Wire, Card, ACH, Mobile")
    customerId: Optional[str] = Field(default=None, description="Fictional synthetic customer ID")
    merchantCategory: Optional[str] = Field(default=None, description="Merchant industry category")
    customerBaseline: Optional[float] = Field(default=None, ge=0.0, description="Customer historical average amount")
    recentTransactionCount: Optional[int] = Field(default=None, ge=0, description="Transaction velocity in last 1hr")
    timeSincePreviousSeconds: Optional[int] = Field(default=None, ge=0, description="Seconds since prior transaction")
    locationCountry: Optional[str] = Field(default=None, description="Originating ISO country code")

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class PredictionResponse(BaseModel):
    transactionId: Optional[str] = None
    riskScore: int = Field(..., ge=0, le=100)
    riskLevel: RiskLevel
    modelProbability: float = Field(..., ge=0.0, le=1.0)
    recommendedAction: str
    indicators: List[str]
    reviewStatus: Optional[ReviewStatus] = None
    inferenceLatencyMs: float
    modelVersion: str
    syntheticDisclosure: str = Field(
        default="Synthetic demonstration benchmark. Decision guidance is advisory.",
        description="Scientific disclosure"
    )


class SimulationRequest(BaseModel):
    scenario: Optional[str] = Field(
        default=None,
        description="Optional scenario: normal | unusual_amount | velocity_burst | elevated_device_risk | cross_border_wire"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional random seed for deterministic reproduction"
    )


class SimulationResponse(BaseModel):
    transaction: Transaction
    alert: Optional[Alert] = None
    inferenceLatencyMs: float
    processingLatencyMs: float
    scenario: str
    syntheticDisclosure: str = Field(
        default="Synthetic demonstration benchmark. Decision guidance is advisory.",
        description="Scientific disclosure"
    )




class ModelPerformance(BaseModel):
    status: str = Field(..., description="Status of model evaluation, e.g., 'pending_evaluation' or 'ready'")
    modelVersion: str = Field(..., description="Model identifier or version string")
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1Score: Optional[float] = None
    falsePositiveRate: Optional[float] = None
    prAuc: Optional[float] = None
    confusionMatrix: Optional[Dict[str, int]] = None
    datasetDisclosures: str = Field(
        ...,
        description="Transparency statement clarifying dataset origin and evaluation conditions"
    )


class AuditRecord(BaseModel):
    id: str
    timestamp: str
    action: str
    details: str
    actor: str = "system"


class IBMZAdapterStatus(BaseModel):
    status: str = Field(..., description="unconfigured | unavailable | connected")
    connection: str = Field(..., description="Type of connection or 'none'")
    details: str = Field(..., description="Accurate disclosure of current IBM Z adapter state")


class HealthResponse(BaseModel):
    status: str
    version: str
    uptimeSeconds: float
    modelStatus: str
    databaseStatus: str
    ibmZAdapter: IBMZAdapterStatus
