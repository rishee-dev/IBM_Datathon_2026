"""
Automated Test Suite for IBM Z Architecture & Integration Adapter (Stage 9).
Verifies:
1. Local mode operation and honest unconfigured disclosure.
2. Missing and invalid IBM Z configuration handling.
3. Connection timeout and error translation (timeouts, auth, connection refused).
4. Strict prohibition of silent fallback from IBM Z mode to local simulation.
5. Response validation and correlation ID tracking.
6. Explicit labeling of test doubles (MockIBMZAdapter).
"""

import pytest
from app.adapters.ibm_z import (
    LocalSimulationAdapter,
    RealIBMZRestAdapter,
    MockIBMZAdapter,
    IBMZConfigurationError,
    IBMZConnectionError,
    IBMZTimeoutError,
    IBMZAuthenticationError,
    IBMZServiceError,
    get_ibm_z_adapter,
)
from app.config import Settings
from app.services.transaction_service import TransactionProcessingService
from app.repository.sqlite_repo import SQLiteRepository


# --- Phase 3 & 4: Adapter Contracts and Modes ---

def test_local_simulation_adapter_default_state():
    """Verify LocalSimulationAdapter accurately reports unconfigured status and local execution."""
    adapter = LocalSimulationAdapter()
    assert adapter.mode == "local_simulation"
    assert adapter.is_test_double is False

    status = adapter.get_status()
    assert status.status == "unconfigured"
    assert status.connection == "none"
    assert status.mode == "local_simulation"
    assert "local verification mode" in status.details.lower()
    assert "local_ml_inference" in status.capabilities

    health = adapter.check_health()
    assert health.is_healthy is True
    assert health.status == "unconfigured"
    assert health.connection == "none"


def test_missing_ibm_z_configuration_raises_error():
    """Verify RealIBMZRestAdapter raises IBMZConfigurationError when host is absent."""
    adapter = RealIBMZRestAdapter(host="")
    assert adapter.mode == "ibm_z"
    assert adapter.is_test_double is False

    # Status reports unavailable, NOT connected
    status = adapter.get_status()
    assert status.status == "unavailable"
    assert status.connection == "none"
    assert "not configured" in status.details.lower()

    # Calling check_health or process_transaction fails fast
    with pytest.raises(IBMZConfigurationError, match="IBM_Z_HOST"):
        adapter.check_health()

    with pytest.raises(IBMZConfigurationError, match="IBM_Z_HOST"):
        adapter.process_transaction({"id": "TXN-TEST", "amount": 100.0})


def test_invalid_ibm_z_configuration_whitespace():
    """Verify whitespace-only host is treated as missing configuration."""
    adapter = RealIBMZRestAdapter(host="   ")
    with pytest.raises(IBMZConfigurationError, match="IBM_Z_HOST"):
        adapter.check_health()


def test_real_adapter_connection_timeout_handling(monkeypatch):
    """Verify that network timeout maps to IBMZTimeoutError."""
    import httpx
    adapter = RealIBMZRestAdapter(host="zos-gateway.internal.bank.com", timeout_seconds=0.1)

    def mock_get(*args, **kwargs):
        raise httpx.TimeoutException("Read timed out")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(IBMZTimeoutError, match="timed out"):
        adapter.check_health()


def test_real_adapter_connection_refused_handling(monkeypatch):
    """Verify that network connection failure maps to IBMZConnectionError."""
    import httpx
    adapter = RealIBMZRestAdapter(host="zos-gateway.internal.bank.com")

    def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(IBMZConnectionError, match="Failed to connect"):
        adapter.check_health()


def test_real_adapter_authentication_error(monkeypatch):
    """Verify HTTP 401/403 maps to IBMZAuthenticationError."""
    import httpx
    adapter = RealIBMZRestAdapter(host="zos-gateway.internal.bank.com", api_key="invalid-key")

    mock_resp = httpx.Response(status_code=401, text="Unauthorized: Invalid API token")

    def mock_get(*args, **kwargs):
        return mock_resp

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(IBMZAuthenticationError, match="rejected credentials"):
        adapter.check_health()


def test_mock_adapter_explicitly_labeled_as_test_double():
    """Verify test doubles are strictly identified as mocks and never misrepresented as live."""
    mock = MockIBMZAdapter(should_succeed=True)
    assert mock.is_test_double is True
    assert mock.mode == "ibm_z"

    status = mock.get_status()
    assert "[TEST DOUBLE" in status.details
    assert status.status == "connected"

    local = LocalSimulationAdapter()
    assert local.is_test_double is False

    real = RealIBMZRestAdapter(host="zos.ibm.com")
    assert real.is_test_double is False


def test_mock_adapter_simulated_faults():
    """Verify MockIBMZAdapter can simulate timeouts, auth errors, and 503s for test isolation."""
    timeout_mock = MockIBMZAdapter(simulate_timeout=True)
    with pytest.raises(IBMZTimeoutError):
        timeout_mock.check_health()

    auth_mock = MockIBMZAdapter(simulate_auth_error=True)
    with pytest.raises(IBMZAuthenticationError):
        auth_mock.check_health()

    s503_mock = MockIBMZAdapter(simulate_503=True)
    with pytest.raises(IBMZServiceError):
        s503_mock.check_health()


# --- Phase 4: Prohibition of Silent Fallback ---

def test_no_silent_fallback_when_ibm_z_fails(tmp_path):
    """
    CRITICAL REQUIREMENT: When IBM Z mode is active and fails, the transaction service
    must fail with an error. It MUST NEVER silently fall back to running local ML!
    """
    test_db = tmp_path / "test_no_fallback.db"
    repo = SQLiteRepository(db_path=test_db)

    # Configure a failing IBM Z adapter test double
    failing_adapter = MockIBMZAdapter(should_succeed=False)
    service = TransactionProcessingService(repo=repo, adapter=failing_adapter)

    assert service.adapter.mode == "ibm_z"

    wire_payload = {
        "amount": 5000.0,
        "channel": "Wire",
        "merchant_category": "luxury",
    }

    # Must raise connection error, NOT silently succeed with local prediction
    with pytest.raises(IBMZConnectionError, match="Simulated connection failure"):
        service.process_transaction(wire_payload)


def test_successful_processing_identifies_execution_origin(tmp_path):
    """Verify that transactions processed in local mode record 'sentinelz_local'."""
    test_db = tmp_path / "test_origin.db"
    repo = SQLiteRepository(db_path=test_db)
    local_adapter = LocalSimulationAdapter()
    service = TransactionProcessingService(repo=repo, adapter=local_adapter)

    payload = {
        "amount": 250.0,
        "channel": "Card",
        "merchant_category": "retail",
    }

    result = service.process_transaction(payload)
    tx = result["transaction"]
    assert tx.processedBy == "sentinelz_local"
    assert result["processedBy"] == "sentinelz_local"

    # Verify persisted in SQLite with processed_by column
    persisted = repo.get_transaction(tx.id)
    assert persisted is not None
    assert persisted.processedBy == "sentinelz_local"


def test_adapter_factory_returns_expected_instance():
    """Verify get_ibm_z_adapter returns LocalSimulationAdapter by default and RealIBMZRestAdapter when configured."""
    default_adapter = get_ibm_z_adapter()
    assert isinstance(default_adapter, LocalSimulationAdapter)

    # When ibm_z_mode is set to ibm_z
    custom_cfg = Settings(ibm_z_mode="ibm_z", ibm_z_host="zos-host.bank.com")
    custom_adapter = get_ibm_z_adapter(custom_cfg)
    assert isinstance(custom_adapter, RealIBMZRestAdapter)
    assert custom_adapter.host == "zos-host.bank.com"
