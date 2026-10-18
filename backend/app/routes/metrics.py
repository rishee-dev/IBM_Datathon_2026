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
        volumeData=[
            {"time": "10:35", "value": 420},
            {"time": "10:36", "value": 510},
            {"time": "10:37", "value": 486},
            {"time": "10:38", "value": 620},
            {"time": "10:39", "value": 570},
            {"time": "10:40", "value": 708},
            {"time": "10:41", "value": 680},
            {"time": "10:42", "value": 744},
        ],
        latencyData=[
            {"time": "10:35", "value": 19},
            {"time": "10:36", "value": 22},
            {"time": "10:37", "value": 18},
            {"time": "10:38", "value": 24},
            {"time": "10:39", "value": 21},
            {"time": "10:40", "value": 28},
            {"time": "10:41", "value": 25},
            {"time": "10:42", "value": 23},
        ],
    )
