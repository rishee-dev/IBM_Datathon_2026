"""
Alerts endpoint providing analyst queue management.
Backed by SQLiteRepository for persistent alert tracking.
"""

from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas import Alert, ReviewStatus
from app.repository.sqlite_repo import sqlite_repo

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=List[Alert])
def list_alerts(
    alert_status: Optional[ReviewStatus] = Query(default=None, alias="status", description="Filter by review status")
) -> List[Alert]:
    """
    Returns alerts for the priority queue. Matches frontend Alert[] contract
    and reflects newly generated alerts from live transaction processing.
    """
    return sqlite_repo.list_alerts(status=alert_status)
