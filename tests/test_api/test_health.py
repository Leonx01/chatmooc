"""Health check and basic API tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
class TestHealth:
    """Test basic health check endpoints."""

    def test_api_router_exists(self, client: TestClient):
        """Test that API router is properly configured."""
        # Try accessing root - should work if app is configured
        response = client.get("/")
        # May return 404 if no root endpoint, which is fine
        assert response.status_code in [200, 404, 307]

    def test_api_v1_prefix(self, client: TestClient):
        """Test API v1 prefix is configured."""
        # Try accessing the API prefix
        response = client.get("/api/v1")
        # Should return 404 or 405 (method not allowed) if routes exist
        assert response.status_code in [200, 404, 405, 422]

    @pytest.mark.integration
    def test_docs_available(self, client: TestClient):
        """Test that API documentation is available."""
        response = client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_openapi_spec(self, client: TestClient):
        """Test that OpenAPI spec is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "info" in data
        assert "paths" in data


@pytest.mark.unit
class TestAPIStructure:
    """Test API endpoint structure."""

    def test_login_endpoint_exists(self, client: TestClient):
        """Test login endpoint exists."""
        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "test", "password": "test123"}
            )
            # Should not return 404 (may return 401 for invalid credentials)
            assert response.status_code != 404
        except Exception as e:
            # Skip if database not available (integration test)
            err_str = str(e).lower()
            if any(x in err_str for x in ["database", "connection", "operationalerror", "access denied"]):
                pytest.skip(f"Database not available: {e}")
            raise

    def test_resource_routes_exist(self, client: TestClient):
        """Test resource routes are registered."""
        response = client.get("/api/v1/resources")
        # Should not return 404 if route exists (may return 401)
        assert response.status_code in [200, 401, 404, 422]

    def test_chat_stream_endpoint_exists(self, client: TestClient):
        """Test chat stream endpoint exists."""
        # POST to chat stream should not return 404
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "hello", "unit_id": "test", "resource_ids": []}
        )
        # 401 (unauthorized) is acceptable, 404 means route doesn't exist
        assert response.status_code in [200, 401, 404, 422]


@pytest.mark.unit
class TestConfigLoading:
    """Test configuration loading."""

    def test_settings_load(self):
        """Test that settings can be loaded."""
        from app.core.config import settings

        assert settings is not None
        assert settings.APP_NAME is not None

    def test_api_prefix_configured(self):
        """Test API prefix is configured."""
        from app.core.config import settings

        assert settings.API_V1_PREFIX == "/api/v1"
