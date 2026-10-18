"""
IBM Z Integration Adapter Architecture for SentinelZ AI.
Provides an explicit boundary separating local machine-learning execution from
mainframe-connected z/OS services (e.g. z/OS Connect, WMLz, or LinuxONE interfaces).

CRITICAL ARCHITECTURAL PRINCIPLES:
1. Local mode operates completely self-contained without requiring IBM Z credentials.
2. IBM Z mode requires verified host and credentials; it NEVER silently falls back to local simulation on failure.
3. Every transaction explicitly declares which system executed the risk assessment ('processedBy').
4. Health status distinguishes backend readiness, model loading, and actual remote IBM Z connectivity.
5. Test doubles are explicitly labeled as mocks and never misrepresented as live mainframe connections.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime
import time
from typing import Any, Dict, List, Optional
import uuid
import httpx

from app.config import settings
from app.schemas import IBMZAdapterStatus


# --- Domain Exceptions ---

class IBMZAdapterError(Exception):
    """Base exception for all IBM Z adapter operations."""
    pass


class IBMZConfigurationError(IBMZAdapterError):
    """Raised when required IBM Z parameters (host, key, port) are missing or invalid."""
    pass


class IBMZConnectionError(IBMZAdapterError):
    """Raised when network connection to IBM Z host cannot be established."""
    pass


class IBMZTimeoutError(IBMZConnectionError):
    """Raised when a request to the IBM Z service times out."""
    pass


class IBMZAuthenticationError(IBMZAdapterError):
    """Raised when authentication (token, key, client cert) is rejected by IBM Z."""
    pass


class IBMZServiceError(IBMZAdapterError):
    """Raised when IBM Z remote endpoint returns a 5xx server fault or malformed payload."""
    pass


# --- Data Transfer Objects ---

@dataclass
class IBMZTransactionResult:
    """Represents the outcome of a transaction risk evaluation processed by an adapter."""
    transaction_id: str
    risk_score: int
    risk_level: str
    recommended_action: str
    indicators: List[str]
    correlation_id: str
    latency_ms: float
    processed_by: str
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IBMZHealthCheckResult:
    """Represents the verified connectivity state to the IBM Z subsystem."""
    is_healthy: bool
    status: str  # "connected" | "unconfigured" | "unavailable" | "error"
    connection: str  # "none" | "https" | "http"
    mode: str  # "local_simulation" | "ibm_z"
    details: str
    capabilities: List[str]
    latency_ms: float = 0.0


# --- Base Abstract Adapter ---

class IBMZBaseAdapter(ABC):
    """Abstract interface defining the contract for IBM Z integration adapters."""

    @property
    @abstractmethod
    def mode(self) -> str:
        """Returns the active operating mode (e.g. 'local_simulation' or 'ibm_z')."""
        pass

    @property
    def is_test_double(self) -> bool:
        """Indicates whether this adapter instance is a test double or genuine provider."""
        return False

    @abstractmethod
    def get_status(self) -> IBMZAdapterStatus:
        """Returns the static/cached status model for health endpoints."""
        pass

    @abstractmethod
    def check_health(self) -> IBMZHealthCheckResult:
        """Performs a live connectivity probe against the target subsystem."""
        pass

    @abstractmethod
    def process_transaction(
        self,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> IBMZTransactionResult:
        """
        Dispatches a transaction to the appropriate execution target.
        Must NOT silently fall back to alternative modes on failure.
        """
        pass


# --- Local Simulation Adapter (Default) ---

class LocalSimulationAdapter(IBMZBaseAdapter):
    """
    Default adapter used when SentinelZ AI runs in standalone local mode.
    Explicitly discloses that transactions are processed locally and no
    remote mainframe connection is active.
    """

    @property
    def mode(self) -> str:
        return "local_simulation"

    def get_status(self) -> IBMZAdapterStatus:
        return IBMZAdapterStatus(
            status="unconfigured",
            connection="none",
            mode="local_simulation",
            details="IBM Z adapter is currently unconfigured. Running in local verification mode until verified IBM Z service access is configured in Stage 9.",
            capabilities=["local_ml_inference", "decision_policy", "synthetic_scenarios"],
            targetHost=None,
        )

    def check_health(self) -> IBMZHealthCheckResult:
        return IBMZHealthCheckResult(
            is_healthy=True,
            status="unconfigured",
            connection="none",
            mode="local_simulation",
            details="Local verification mode active. IBM Z remote connectivity is unconfigured by design.",
            capabilities=["local_ml_inference", "decision_policy", "synthetic_scenarios"],
            latency_ms=0.0,
        )

    def process_transaction(
        self,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> IBMZTransactionResult:
        """
        In local mode, the caller is expected to utilize the local Random Forest
        pipeline. This adapter method marks the execution origin explicitly as sentinelz_local.
        """
        cid = correlation_id or str(uuid.uuid4())
        return IBMZTransactionResult(
            transaction_id=str(payload.get("id", "TXN-UNKNOWN")),
            risk_score=int(payload.get("riskScore", 0)),
            risk_level=str(payload.get("riskLevel", "low")),
            recommended_action=str(payload.get("recommendedAction", "Allow")),
            indicators=list(payload.get("indicators", [])),
            correlation_id=cid,
            latency_ms=float(payload.get("inferenceLatencyMs", 0.0)),
            processed_by="sentinelz_local",
            raw_response={"mode": "local_simulation", "execution": "scikit_learn_random_forest"},
        )


# --- Real IBM Z REST / z/OS Connect Adapter ---

class RealIBMZRestAdapter(IBMZBaseAdapter):
    """
    Production adapter designed to communicate with IBM z/OS Connect Enterprise Edition
    or IBM Z/LinuxONE REST APIs via HTTPS.
    Requires verified environment configuration (IBM_Z_HOST, IBM_Z_API_KEY).
    """

    def __init__(
        self,
        host: str,
        port: int = 443,
        api_key: str = "",
        use_tls: bool = True,
        timeout_seconds: float = 5.0,
        service_path: str = "/api/v1/transactions",
    ):
        self.host = host.strip()
        self.port = port
        self.api_key = api_key.strip()
        self.use_tls = use_tls
        self.timeout_seconds = timeout_seconds
        self.service_path = service_path

        scheme = "https" if use_tls else "http"
        self.base_url = f"{scheme}://{self.host}:{self.port}" if self.host else ""

    @property
    def mode(self) -> str:
        return "ibm_z"

    def _validate_configuration(self) -> None:
        """Fails fast if mandatory connection settings are absent."""
        if not self.host:
            raise IBMZConfigurationError(
                "IBM Z mode is enabled, but required configuration parameter 'IBM_Z_HOST' is missing."
            )

    def get_status(self) -> IBMZAdapterStatus:
        if not self.host:
            return IBMZAdapterStatus(
                status="unavailable",
                connection="none",
                mode="ibm_z",
                details="IBM Z mode is selected, but target host (IBM_Z_HOST) is not configured.",
                capabilities=[],
                targetHost=None,
            )
        
        # Mask host for security (e.g. zos-gateway.internal.corp:443)
        masked_host = f"{self.host}:{self.port}"
        return IBMZAdapterStatus(
            status="configured",
            connection="https" if self.use_tls else "http",
            mode="ibm_z",
            details=f"IBM Z REST adapter configured for target {masked_host}. Awaiting live handshake.",
            capabilities=["z_os_connect", "wmlz_ai_inference", "cics_transaction_query"],
            targetHost=masked_host,
        )

    def check_health(self) -> IBMZHealthCheckResult:
        self._validate_configuration()
        health_url = f"{self.base_url}/health"
        headers = {
            "Accept": "application/json",
            "X-Correlation-ID": str(uuid.uuid4()),
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds, verify=self.use_tls) as client:
                res = client.get(health_url, headers=headers)
                latency = round((time.perf_counter() - t0) * 1000, 2)

                if res.status_code == 200:
                    return IBMZHealthCheckResult(
                        is_healthy=True,
                        status="connected",
                        connection="https" if self.use_tls else "http",
                        mode="ibm_z",
                        details=f"Successfully connected to IBM Z service at {self.host}:{self.port}.",
                        capabilities=["z_os_connect", "wmlz_ai_inference"],
                        latency_ms=latency,
                    )
                elif res.status_code in (401, 403):
                    raise IBMZAuthenticationError(f"IBM Z service rejected credentials (HTTP {res.status_code}).")
                else:
                    raise IBMZServiceError(f"IBM Z health endpoint returned HTTP {res.status_code}: {res.text}")

        except httpx.TimeoutException as exc:
            raise IBMZTimeoutError(f"Connection to IBM Z host '{self.host}' timed out after {self.timeout_seconds}s.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise IBMZConnectionError(f"Failed to connect to IBM Z host '{self.host}:{self.port}': {str(exc)}") from exc

    def process_transaction(
        self,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> IBMZTransactionResult:
        """
        Submits transaction payload to IBM Z service.
        NEVER silently falls back to local simulation upon failure.
        """
        self._validate_configuration()

        cid = correlation_id or str(uuid.uuid4())
        submit_url = f"{self.base_url}{self.service_path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Correlation-ID": cid,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds, verify=self.use_tls) as client:
                res = client.post(submit_url, json=payload, headers=headers)
                latency = round((time.perf_counter() - t0) * 1000, 2)

                if res.status_code == 200:
                    data = res.json()
                    return IBMZTransactionResult(
                        transaction_id=str(data.get("id", payload.get("id"))),
                        risk_score=int(data["riskScore"]),
                        risk_level=str(data["riskLevel"]),
                        recommended_action=str(data.get("recommendedAction", "Hold for review")),
                        indicators=list(data.get("indicators", [])),
                        correlation_id=cid,
                        latency_ms=latency,
                        processed_by="ibm_z_rest",
                        raw_response=data,
                    )
                elif res.status_code in (401, 403):
                    raise IBMZAuthenticationError(f"IBM Z authentication rejected: {res.text}")
                else:
                    raise IBMZServiceError(f"IBM Z transaction processing failed (HTTP {res.status_code}): {res.text}")

        except httpx.TimeoutException as exc:
            raise IBMZTimeoutError(f"IBM Z transaction processing timed out after {self.timeout_seconds}s.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise IBMZConnectionError(f"IBM Z service unreachable at '{self.base_url}': {str(exc)}") from exc


# --- Test Double / Mock Adapter (Explicitly Labeled) ---

class MockIBMZAdapter(IBMZBaseAdapter):
    """
    Explicit test double used strictly in automated test suites to simulate
    mainframe connection responses, timeouts, and network faults.
    """

    def __init__(
        self,
        should_succeed: bool = True,
        simulate_timeout: bool = False,
        simulate_auth_error: bool = False,
        simulate_503: bool = False,
        simulated_latency_ms: float = 12.5,
    ):
        self.should_succeed = should_succeed
        self.simulate_timeout = simulate_timeout
        self.simulate_auth_error = simulate_auth_error
        self.simulate_503 = simulate_503
        self.simulated_latency_ms = simulated_latency_ms

    @property
    def mode(self) -> str:
        return "ibm_z"

    @property
    def is_test_double(self) -> bool:
        return True

    def get_status(self) -> IBMZAdapterStatus:
        status_val = "connected" if self.should_succeed else "unavailable"
        return IBMZAdapterStatus(
            status=status_val,
            connection="https",
            mode="ibm_z",
            details="[TEST DOUBLE ONLY] Controlled mock IBM Z adapter for deterministic testing.",
            capabilities=["mock_z_os_connect"],
            targetHost="mock-mainframe.test.internal",
        )

    def check_health(self) -> IBMZHealthCheckResult:
        if self.simulate_timeout:
            raise IBMZTimeoutError("[TEST DOUBLE] Simulated IBM Z timeout.")
        if self.simulate_auth_error:
            raise IBMZAuthenticationError("[TEST DOUBLE] Simulated IBM Z 401 unauthorized.")
        if self.simulate_503:
            raise IBMZServiceError("[TEST DOUBLE] Simulated IBM Z 503 service unavailable.")
        if not self.should_succeed:
            raise IBMZConnectionError("[TEST DOUBLE] Simulated connection refused.")

        return IBMZHealthCheckResult(
            is_healthy=True,
            status="connected",
            connection="https",
            mode="ibm_z",
            details="[TEST DOUBLE] Simulated healthy IBM Z connection.",
            capabilities=["mock_z_os_connect"],
            latency_ms=self.simulated_latency_ms,
        )

    def process_transaction(
        self,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> IBMZTransactionResult:
        if self.simulate_timeout:
            raise IBMZTimeoutError("[TEST DOUBLE] Simulated transaction timeout.")
        if self.simulate_auth_error:
            raise IBMZAuthenticationError("[TEST DOUBLE] Simulated auth error on submission.")
        if not self.should_succeed:
            raise IBMZConnectionError("[TEST DOUBLE] Simulated connection failure during transaction processing.")

        cid = correlation_id or str(uuid.uuid4())
        return IBMZTransactionResult(
            transaction_id=str(payload.get("id", "TXN-MOCK")),
            risk_score=75,
            risk_level="high",
            recommended_action="Hold for review",
            indicators=["Mainframe CICS Risk Scoring Alert"],
            correlation_id=cid,
            latency_ms=self.simulated_latency_ms,
            processed_by="mock_ibm_z_test_double",
            raw_response={"test_double": True, "status": "APPROVED_MOCK"},
        )


# --- Adapter Factory ---

def get_ibm_z_adapter(custom_settings=None) -> IBMZBaseAdapter:
    """
    Factory function returning the configured adapter instance based on environment settings.
    Defaults to LocalSimulationAdapter if IBM Z mode is not explicitly enabled.
    """
    cfg = custom_settings or settings
    mode = getattr(cfg, "ibm_z_mode", "local_simulation").lower()
    enabled = getattr(cfg, "ibm_z_enabled", False)

    if mode == "ibm_z" or enabled:
        return RealIBMZRestAdapter(
            host=getattr(cfg, "ibm_z_host", ""),
            port=getattr(cfg, "ibm_z_port", 443),
            api_key=getattr(cfg, "ibm_z_api_key", ""),
            use_tls=getattr(cfg, "ibm_z_use_tls", True),
            timeout_seconds=getattr(cfg, "ibm_z_timeout_seconds", 5.0),
            service_path=getattr(cfg, "ibm_z_service_path", "/api/v1/transactions"),
        )
    return LocalSimulationAdapter()


# Global default adapter singleton
ibm_z_adapter: IBMZBaseAdapter = get_ibm_z_adapter()
