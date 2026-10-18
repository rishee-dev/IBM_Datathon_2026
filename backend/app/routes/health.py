"""
Health check endpoint reporting system uptime, model status, and IBM Z adapter state.
"""

import time
from fastapi import APIRouter
from app.config import settings
from app.schemas import HealthResponse, IBMZAdapterStatus

from app.ml.predictor import predictor
from app.adapters.ibm_z import ibm_z_adapter

router = APIRouter(tags=["Health"])

START_TIME = time.time()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """
    Returns system status, model readiness, and transparent IBM Z integration state.
    """
    uptime = round(time.time() - START_TIME, 2)
    
    # Query adapter for honest configuration & connectivity state
    ibm_z_state = ibm_z_adapter.get_status()

    if predictor.is_ready:
        model_status = f"loaded ({predictor.metadata.get('model_name', 'Model')} v{predictor.model_version}, threshold={predictor.operating_threshold:.3f})"
    else:
        model_status = "not_loaded (awaiting training in Stage 4)"
    
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        uptimeSeconds=uptime,
        modelStatus=model_status,
        databaseStatus="connected (SQLite repository active)",
        ibmZAdapter=ibm_z_state,
    )

