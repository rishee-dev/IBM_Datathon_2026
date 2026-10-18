"""
Transaction Processing Service for SentinelZ AI.
Orchestrates input validation, feature preparation, model inference, decision engine evaluation,
policy-based alert generation, distinct latency measurement, and SQLite persistence.
"""

import datetime
import time
import uuid
from typing import Any, Dict, Optional

from app.schemas import Transaction, Alert, AuditRecord, Channel, RiskLevel, ReviewStatus
from app.ml.predictor import predictor
from app.engine.decision_engine import decision_engine
from app.repository.sqlite_repo import sqlite_repo
from app.services.scenarios import build_scenario_payload


from app.adapters.ibm_z import ibm_z_adapter, IBMZBaseAdapter


class TransactionProcessingService:
    """
    Core service orchestrating real-time transaction ingestion and intelligence.
    Supports explicit operational modes: local machine-learning execution or
    direct mainframe processing via IBMZBaseAdapter.
    """

    def __init__(self, repo=None, pred=None, engine=None, adapter: Optional[IBMZBaseAdapter] = None):
        self.repo = repo or sqlite_repo
        self.predictor = pred or predictor
        self.engine = engine or decision_engine
        self.adapter = adapter or ibm_z_adapter

    def process_transaction(
        self,
        raw_payload: Dict[str, Any],
        scenario_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end transaction processing:
        1. Validates and normalizes input.
        2. Assigns a unique transaction ID.
        3. Runs inference through active engine (local model or IBM Z adapter).
        4. Applies DecisionEngine policy rules and derives evidence indicators.
        5. Generates an Alert if the policy indicates high/medium risk.
        6. Atomically persists transaction and alert to SQLite.
        7. Returns processed transaction, generated alert, latency metrics, and execution origin.
        """
        t_start = time.perf_counter()

        # 1. Validation & normalization
        amount = float(raw_payload.get("amount", 0.0))
        if amount <= 0.0:
            raise ValueError(f"Transaction amount must be strictly positive, got {amount}")

        channel_val = raw_payload.get("channel", "Card")
        try:
            channel = Channel(channel_val)
        except ValueError:
            raise ValueError(f"Invalid payment channel '{channel_val}'. Must be one of: Wire, Card, ACH, Mobile")

        # 2. Unique ID and timestamps
        tx_id = raw_payload.get("id") or self.repo.generate_next_transaction_id()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        timestamp_str = raw_payload.get("timestamp") or now_dt.strftime("%H:%M:%S.%f")[:-3]
        processing_ts = now_dt.strftime("%H:%M:%S.%f")[:-3]

        pred_features = dict(raw_payload)
        pred_features["id"] = tx_id
        pred_features["amount"] = amount
        pred_features["channel"] = channel.value

        # 3. Model Inference: Local or IBM Z mode
        if self.adapter.mode == "ibm_z":
            # Direct IBM Z execution mode
            # Under NO circumstances silently fall back to local mode on failure!
            ibm_result = self.adapter.process_transaction(pred_features)
            risk_score = ibm_result.risk_score
            risk_level = RiskLevel(ibm_result.risk_level.lower())
            recommended_action = ibm_result.recommended_action
            indicators = ibm_result.indicators
            inference_latency_ms = ibm_result.latency_ms
            processed_by = ibm_result.processed_by
        else:
            # Standalone Local Simulation Mode
            if not self.predictor.is_ready:
                raise RuntimeError("Machine-learning model is not loaded. Train the model via app.ml.train first.")

            pred_result = self.predictor.predict_transaction(pred_features)
            risk_score = pred_result["riskScore"]
            risk_level = RiskLevel(pred_result["riskLevel"])
            recommended_action = pred_result["recommendedAction"]
            indicators = pred_result["indicators"]
            inference_latency_ms = float(pred_result["inferenceLatencyMs"])
            processed_by = "sentinelz_local"

        # 4. Form Transaction entity
        tx = Transaction(
            id=tx_id,
            timestamp=timestamp_str,
            amount=amount,
            channel=channel,
            riskScore=risk_score,
            riskLevel=risk_level,
            recommendedAction=recommended_action,
            indicators=indicators,
            processingTimestamp=processing_ts,
            processedBy=processed_by,
        )

        # 5. Policy-Driven Alert Generation
        alert: Optional[Alert] = None
        # Alerts are generated when risk level is high or medium (action requires triage/step-up)
        if tx.riskLevel in [RiskLevel.HIGH, RiskLevel.MEDIUM] or tx.recommendedAction == "Hold for review":
            alert_id = self.repo.generate_next_alert_id()
            
            # Construct meaningful, evidence-based reason
            primary_reason = tx.indicators[0] if tx.indicators else "High-risk behavioral anomaly"
            if len(tx.indicators) > 1 and tx.indicators[0] != "Normal activity pattern":
                reason_text = f"{tx.indicators[0]} ({tx.indicators[1]})"
            else:
                reason_text = primary_reason

            # Recommended next step based on channel and risk signals
            if channel == Channel.WIRE:
                next_step = "Validate origin and beneficiary"
            elif channel == Channel.CARD:
                next_step = "Confirm customer intent"
            elif any("velocity" in ind.lower() or "cadence" in ind.lower() for ind in tx.indicators):
                next_step = "Verify session tokens and customer credentials"
            else:
                next_step = "Request enhanced due diligence"

            alert = Alert(
                id=alert_id,
                transactionId=tx.id,
                riskScore=tx.riskScore,
                reason=reason_text,
                nextStep=next_step,
                status=ReviewStatus.NEEDS_REVIEW,
            )

        # 6. End-to-end Processing Latency Measurement
        processing_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # 7. Persistence with auto-generated ID collision recovery
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.repo.save_transaction(
                    tx=tx,
                    inference_latency_ms=inference_latency_ms,
                    processing_latency_ms=processing_latency_ms,
                )
                if alert:
                    self.repo.save_alert(alert)
                break
            except Exception as err:
                import sqlite3
                if isinstance(err, sqlite3.IntegrityError) and not raw_payload.get("id") and attempt < max_retries - 1:
                    new_id = self.repo.generate_next_transaction_id()
                    tx = tx.model_copy(update={"id": new_id})
                    if alert:
                        alert = alert.model_copy(update={"transactionId": new_id})
                    continue
                raise

        # Record audit log with execution origin
        audit_record = AuditRecord(
            id=f"AUD-{uuid.uuid4().hex[:6].upper()}",
            timestamp=processing_ts,
            action="TRANSACTION_PROCESSED",
            details=f"Processed {tx.id} (${tx.amount:.2f} {tx.channel.value}) via {processed_by}: riskScore={tx.riskScore} ({tx.riskLevel.value}) -> {tx.recommendedAction}",
            actor=processed_by,
        )
        self.repo.save_audit_log(audit_record)

        return {
            "transaction": tx,
            "alert": alert,
            "inferenceLatencyMs": inference_latency_ms,
            "processingLatencyMs": processing_latency_ms,
            "scenario": scenario_name or "custom",
            "syntheticDisclosure": "Synthetic demonstration benchmark. Decision guidance is advisory.",
            "processedBy": processed_by,
        }

    def simulate_transaction(
        self,
        scenario: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates a synthetic scenario transaction and processes it through the live pipeline.
        """
        scenario_data = build_scenario_payload(scenario=scenario, seed=seed)
        scenario_name = scenario_data.get("scenario", "random")
        return self.process_transaction(raw_payload=scenario_data, scenario_name=scenario_name)


# Global service singleton instance
transaction_service = TransactionProcessingService()
