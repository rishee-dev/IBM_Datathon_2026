import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas import Alert, ReviewStatus, UpdateAlertRequest, AuditRecord
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


@router.patch("/{alert_id}", response_model=Alert)
def update_alert_status(alert_id: str, payload: UpdateAlertRequest) -> Alert:
    """
    Updates the review status of an alert (Needs review -> In review -> Resolved).
    Persisted to SQLite and recorded in the audit trail.
    """
    updated = sqlite_repo.update_alert_status(alert_id, payload.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' was not found"
        )

    # Persist audit log of status transition
    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    sqlite_repo.save_audit_log(
        AuditRecord(
            id=f"AUD-{uuid.uuid4().hex[:6].upper()}",
            timestamp=now_ts,
            action="ALERT_STATUS_UPDATED",
            details=f"Alert {alert_id} (Txn: {updated.transactionId}) status updated to '{payload.status.value}'",
            actor="compliance_analyst",
        )
    )

    return updated
