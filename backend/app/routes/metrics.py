"""
Metrics endpoint providing real-time processing and risk telemetry.
Calculated dynamically from SQLite persistence records.
"""

from fastapi import APIRouter
from app.schemas import Metrics
from app.repository.sqlite_repo import sqlite_repo

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("", response_model=Metrics)
def get_metrics() -> Metrics:
    """
    Returns aggregated KPI metrics and telemetry calculated from stored records.
    Strictly matches frontend Metrics interface in lib/api.ts.
    """
    summary = sqlite_repo.get_metrics_summary()

    return Metrics(
        transactionsProcessed=summary["transactionsProcessed"],
        highRiskTransactions=summary["highRiskTransactions"],
        alertsGenerated=summary["alertsGenerated"],
        averageLatencyMs=summary["averageLatencyMs"],
        volumeData=summary.get("volumeData", []),
        latencyData=summary.get("latencyData", []),
    )

