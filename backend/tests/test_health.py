"""
Automated tests for health endpoint, IBM Z adapter status disclosure, and CORS configuration.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint_success():
    """Verify health endpoint responds with 200 and required fields."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "uptimeSeconds" in data
    assert "modelStatus" in data
    assert "loaded" in data["modelStatus"]


def test_ibm_z_adapter_status_disclosure():
    """Verify that IBM Z adapter is accurately reported as unconfigured and not fabricated."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    adapter = data.get("ibmZAdapter", {})
    assert adapter.get("status") == "unconfigured"
    assert adapter.get("connection") == "none"
    assert "Stage 9" in adapter.get("details", "")


def test_cors_allowed_origin():
    """Verify that configured development origin receives appropriate CORS headers."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_disallowed_origin():
    """Verify that unapproved arbitrary origin is denied CORS headers."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://untrusted-external-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_root_endpoint():
    """Verify that root endpoint provides documentation links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SentinelZ AI Backend"
    assert data["docs"] == "/docs"
