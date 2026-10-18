"""
Adapters package for SentinelZ AI.
Provides clean boundaries between core business logic and external integration providers.
"""

from app.adapters.ibm_z import (
    IBMZBaseAdapter,
    LocalSimulationAdapter,
    RealIBMZRestAdapter,
    MockIBMZAdapter,
    IBMZAdapterError,
    IBMZConfigurationError,
    IBMZConnectionError,
    IBMZTimeoutError,
    IBMZAuthenticationError,
    IBMZServiceError,
    IBMZTransactionResult,
    IBMZHealthCheckResult,
    get_ibm_z_adapter,
    ibm_z_adapter,
)

__all__ = [
    "IBMZBaseAdapter",
    "LocalSimulationAdapter",
    "RealIBMZRestAdapter",
    "MockIBMZAdapter",
    "IBMZAdapterError",
    "IBMZConfigurationError",
    "IBMZConnectionError",
    "IBMZTimeoutError",
    "IBMZAuthenticationError",
    "IBMZServiceError",
    "IBMZTransactionResult",
    "IBMZHealthCheckResult",
    "get_ibm_z_adapter",
    "ibm_z_adapter",
]
