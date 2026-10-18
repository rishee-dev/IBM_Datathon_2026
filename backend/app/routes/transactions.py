"""
Transactions endpoints: fetching transactions, looking up by ID, and simulation pipeline trigger.
Backed by SQLiteRepository and TransactionProcessingService.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import Transaction, RiskLevel, Channel, SimulationRequest, SimulationResponse
from app.repository.sqlite_repo import sqlite_repo
from app.services.transaction_service import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=List[Transaction])
def list_transactions(
    risk_level: Optional[RiskLevel] = Query(default=None, alias="riskLevel", description="Filter by risk level"),
    channel: Optional[Channel] = Query(default=None, description="Filter by payment channel"),
    limit: int = Query(default=50, ge=1, le=500, description="Max number of transactions to return"),
) -> List[Transaction]:
    """
    List transactions with optional filtering by risk level or channel.
    Matches frontend interface Transaction[] and reflects newly ingested records.
    """
    return sqlite_repo.list_transactions(risk_level=risk_level, channel=channel, limit=limit)


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: str) -> Transaction:
    """
    Fetch a single transaction by ID. Returns 404 if not found.
    """
    tx = sqlite_repo.get_transaction(transaction_id)
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' was not found"
        )
    return tx


@router.post("/simulate", response_model=SimulationResponse)
def simulate_transaction(payload: Optional[SimulationRequest] = None) -> SimulationResponse:
    """
    Simulate a new transaction through the end-to-end pipeline:
    Synthetic Input -> Model Inference -> Decision Engine -> Alert Policy -> SQLite Persistence.
    
    Supports scenarios: normal, unusual_amount, velocity_burst, elevated_device_risk, cross_border_wire.
    """
    if not transaction_service.predictor.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine-learning model is not yet trained or loaded. Run model training pipeline first."
        )

    try:
        scenario = payload.scenario if payload else None
        seed = payload.seed if payload else None
        result = transaction_service.simulate_transaction(scenario=scenario, seed=seed)
        return SimulationResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation processing failed: {str(e)}"
        )
