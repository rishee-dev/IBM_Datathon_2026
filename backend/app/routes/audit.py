"""
Audit trail endpoint for compliance and operational tracking.
Backed by SQLiteRepository for persistent audit logs.
"""

from typing import List
from fastapi import APIRouter
from app.schemas import AuditRecord
from app.repository.sqlite_repo import sqlite_repo

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("", response_model=List[AuditRecord])
def list_audit_records() -> List[AuditRecord]:
    """
    Returns audit trail entries for regulatory and system verification.
    Reflects all transaction processing events and security events.
    """
    return sqlite_repo.list_audit_logs()
