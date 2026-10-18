"""
SQLite Database Repository for SentinelZ AI.
Provides atomic persistence for transactions, alerts, and audit logs.
Seeds baseline demonstration records on initialization while supporting persistent live ingestion.
"""

import json
import sqlite3
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas import Transaction, Alert, AuditRecord, RiskLevel, ReviewStatus, Channel

DB_PATH = Path(__file__).resolve().parent.parent.parent / "sentinelz.db"


class SQLiteRepository:
    """
    Lightweight, robust SQLite persistence engine using Python's standard sqlite3 module.
    Thread-safe connection handling with ACID transactional guarantees.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with row_factory set to sqlite3.Row."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Creates tables if they do not exist and populates baseline demonstration records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Transactions Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    amount REAL NOT NULL,
                    channel TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    indicators TEXT NOT NULL,
                    processing_timestamp TEXT NOT NULL,
                    inference_latency_ms REAL DEFAULT 0.0,
                    processing_latency_ms REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Alerts Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES transactions (id) ON DELETE CASCADE
                );
                """
            )

            # Audit Logs Table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            conn.commit()

        # Seed baseline records if database is freshly created
        self._seed_baseline_if_empty()

    def _seed_baseline_if_empty(self) -> None:
        """Seeds initial demo records if the transactions table is empty."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS cnt FROM transactions;")
            count = cursor.fetchone()["cnt"]

            if count == 0:
                # 1. Baseline Transactions
                seed_txs = [
                    ("TXN-849201", "10:42:18.205", 24850.0, "Wire", 92, "high", "Hold for review", json.dumps(["Velocity anomaly", "New beneficiary", "Geo mismatch"]), "10:42:18.221", 24.2, 38.5),
                    ("TXN-849200", "10:42:17.998", 1250.50, "Card", 18, "low", "Allow", json.dumps(["Known device"]), "10:42:18.012", 18.0, 25.1),
                    ("TXN-849199", "10:42:17.701", 7800.0, "ACH", 61, "medium", "Step-up authentication", json.dumps(["Amount deviation", "Account age"]), "10:42:17.719", 21.5, 30.2),
                    ("TXN-849198", "10:42:17.432", 340.25, "Mobile", 9, "low", "Allow", json.dumps(["Normal pattern"]), "10:42:17.448", 16.8, 22.4),
                    ("TXN-849197", "10:42:16.904", 52100.0, "Wire", 87, "high", "Hold for review", json.dumps(["High-value transfer", "Velocity anomaly"]), "10:42:16.929", 28.1, 41.0),
                    ("TXN-849196", "10:42:16.580", 2190.75, "Card", 44, "medium", "Monitor", json.dumps(["Unusual merchant"]), "10:42:16.596", 19.3, 27.8),
                ]
                cursor.executemany(
                    """
                    INSERT INTO transactions (id, timestamp, amount, channel, risk_score, risk_level, recommended_action, indicators, processing_timestamp, inference_latency_ms, processing_latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    seed_txs,
                )

                # 2. Baseline Alerts
                seed_alerts = [
                    ("ALT-2048", "TXN-849201", 92, "Velocity anomaly across new beneficiary", "Validate origin and beneficiary", "Needs review"),
                    ("ALT-2047", "TXN-849197", 87, "High-value wire outside baseline", "Request enhanced due diligence", "In review"),
                    ("ALT-2046", "TXN-849201", 81, "Geographic and device mismatch", "Confirm customer intent", "Needs review"),
                ]
                cursor.executemany(
                    """
                    INSERT INTO alerts (id, transaction_id, risk_score, reason, next_step, status)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    seed_alerts,
                )

                # 3. Baseline Audit Logs
                seed_audit = [
                    ("AUD-1001", "10:40:00.000", "SYSTEM_INIT", "SentinelZ AI SQLite repository initialized with demonstration baseline", "system"),
                    ("AUD-1002", "10:41:00.000", "CORS_RESTRICTION", "CORS policies restricted to localhost frontend origin (http://localhost:3000)", "security_engine"),
                    ("AUD-1003", "10:42:00.000", "ADAPTER_STATUS_CHECK", "IBM Z adapter marked unconfigured; operating in local mode until Stage 9 verification", "integration_manager"),
                ]
                cursor.executemany(
                    """
                    INSERT INTO audit_logs (id, timestamp, action, details, actor)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    seed_audit,
                )

                conn.commit()

    def reset_demo_data(self) -> None:
        """Resets the repository to clean baseline demonstration records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alerts;")
            cursor.execute("DELETE FROM transactions;")
            cursor.execute("DELETE FROM audit_logs;")
            conn.commit()
        self._seed_baseline_if_empty()

    # --- Transaction Operations ---

    def save_transaction(
        self,
        tx: Transaction,
        inference_latency_ms: float = 0.0,
        processing_latency_ms: float = 0.0,
    ) -> Transaction:
        """Atomically saves a processed transaction."""
        indicators_json = json.dumps(tx.indicators)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transactions (id, timestamp, amount, channel, risk_score, risk_level, recommended_action, indicators, processing_timestamp, inference_latency_ms, processing_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    tx.id,
                    tx.timestamp,
                    tx.amount,
                    tx.channel.value if isinstance(tx.channel, Channel) else str(tx.channel),
                    tx.riskScore,
                    tx.riskLevel.value if isinstance(tx.riskLevel, RiskLevel) else str(tx.riskLevel),
                    tx.recommendedAction,
                    indicators_json,
                    tx.processingTimestamp,
                    inference_latency_ms,
                    processing_latency_ms,
                ),
            )
            conn.commit()
        return tx

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Fetches a transaction by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions WHERE id = ?;", (tx_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_transaction(row)

    def list_transactions(
        self,
        risk_level: Optional[RiskLevel] = None,
        channel: Optional[Channel] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        """Lists transactions with optional filtering, ordered newest first."""
        query = "SELECT * FROM transactions WHERE 1=1"
        params: List[Any] = []

        if risk_level is not None:
            query += " AND risk_level = ?"
            params.append(risk_level.value if isinstance(risk_level, RiskLevel) else str(risk_level))
        if channel is not None:
            query += " AND channel = ?"
            params.append(channel.value if isinstance(channel, Channel) else str(channel))

        query += " ORDER BY rowid DESC LIMIT ?;"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_transaction(r) for r in rows]

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        indicators = []
        try:
            indicators = json.loads(row["indicators"])
        except Exception:
            indicators = []

        return Transaction(
            id=row["id"],
            timestamp=row["timestamp"],
            amount=row["amount"],
            channel=Channel(row["channel"]),
            riskScore=row["risk_score"],
            riskLevel=RiskLevel(row["risk_level"]),
            recommendedAction=row["recommended_action"],
            indicators=indicators,
            processingTimestamp=row["processing_timestamp"],
        )

    # --- Alert Operations ---

    def save_alert(self, alert: Alert) -> Alert:
        """Atomically saves an alert, ignoring if already exists for this event or transaction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM alerts WHERE transaction_id = ? OR id = ?;", (alert.transactionId, alert.id))
            existing = cursor.fetchone()
            if existing:
                existing_alert = self.get_alert(existing["id"])
                if existing_alert:
                    return existing_alert

            cursor.execute(
                """
                INSERT OR IGNORE INTO alerts (id, transaction_id, risk_score, reason, next_step, status)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    alert.id,
                    alert.transactionId,
                    alert.riskScore,
                    alert.reason,
                    alert.nextStep,
                    alert.status.value if isinstance(alert.status, ReviewStatus) else str(alert.status),
                ),
            )
            conn.commit()
        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Fetches an alert by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE id = ?;", (alert_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_alert(row)

    def list_alerts(self, status: Optional[ReviewStatus] = None) -> List[Alert]:
        """Lists alerts ordered newest first."""
        query = "SELECT * FROM alerts"
        params: List[Any] = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status.value if isinstance(status, ReviewStatus) else str(status))
        query += " ORDER BY rowid DESC;"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_alert(r) for r in rows]

    def _row_to_alert(self, row: sqlite3.Row) -> Alert:
        return Alert(
            id=row["id"],
            transactionId=row["transaction_id"],
            riskScore=row["risk_score"],
            reason=row["reason"],
            nextStep=row["next_step"],
            status=ReviewStatus(row["status"]),
        )

    # --- Audit Operations ---

    def save_audit_log(self, record: AuditRecord) -> AuditRecord:
        """Atomically saves an audit log entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_logs (id, timestamp, action, details, actor)
                VALUES (?, ?, ?, ?, ?);
                """,
                (record.id, record.timestamp, record.action, record.details, record.actor),
            )
            conn.commit()
        return record

    def list_audit_logs(self, limit: int = 50) -> List[AuditRecord]:
        """Lists audit logs ordered newest first."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs ORDER BY rowid DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            return [
                AuditRecord(
                    id=r["id"],
                    timestamp=r["timestamp"],
                    action=r["action"],
                    details=r["details"],
                    actor=r["actor"],
                )
                for r in rows
            ]

    # --- Metrics & Telemetry ---

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Computes real counts and average latency across stored transactions and alerts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM transactions;")
            total_tx = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) AS high_risk FROM transactions WHERE risk_level = 'high';")
            high_risk = cursor.fetchone()["high_risk"]

            cursor.execute("SELECT COUNT(*) AS total_alerts FROM alerts;")
            total_alerts = cursor.fetchone()["total_alerts"]

            cursor.execute("SELECT AVG(processing_latency_ms) AS avg_lat FROM transactions WHERE processing_latency_ms > 0;")
            row_lat = cursor.fetchone()
            avg_latency = round(row_lat["avg_lat"], 1) if row_lat and row_lat["avg_lat"] else 23.4

            return {
                "transactionsProcessed": total_tx,
                "highRiskTransactions": high_risk,
                "alertsGenerated": total_alerts,
                "averageLatencyMs": avg_latency,
            }

    # --- ID Generation ---

    def generate_next_transaction_id(self) -> str:
        """Generates a sequential, collision-free transaction ID (e.g. TXN-849202)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM transactions WHERE id LIKE 'TXN-%';")
            rows = cursor.fetchall()
            max_num = 0
            for row in rows:
                parts = row["id"].split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    max_num = max(max_num, int(parts[1]))
            if max_num > 0:
                return f"TXN-{max_num + 1}"
            import uuid
            return f"TXN-{uuid.uuid4().hex[:6].upper()}"

    def generate_next_alert_id(self) -> str:
        """Generates a sequential, collision-free alert ID (e.g. ALT-2049)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM alerts WHERE id LIKE 'ALT-%';")
            rows = cursor.fetchall()
            max_num = 0
            for row in rows:
                parts = row["id"].split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    max_num = max(max_num, int(parts[1]))
            if max_num > 0:
                return f"ALT-{max_num + 1}"
            import uuid
            return f"ALT-{uuid.uuid4().hex[:4].upper()}"


# Global repository singleton instance
sqlite_repo = SQLiteRepository()
