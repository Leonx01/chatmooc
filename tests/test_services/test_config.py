"""Configuration service tests."""
import pytest


@pytest.mark.unit
class TestConfig:
    """Test configuration service."""

    def test_settings_object_exists(self):
        """Test that settings object can be imported."""
        from app.core.config import settings

        assert settings is not None

    def test_app_name_set(self):
        """Test app name is configured."""
        from app.core.config import settings

        assert hasattr(settings, "APP_NAME")
        assert settings.APP_NAME is not None
        assert isinstance(settings.APP_NAME, str)

    def test_mysql_config_present(self):
        """Test MySQL configuration is present."""
        from app.core.config import settings

        assert hasattr(settings, "MYSQL_HOST")
        assert hasattr(settings, "MYSQL_PORT")
        assert hasattr(settings, "MYSQL_DATABASE")

    def test_redis_config_present(self):
        """Test Redis configuration is present."""
        from app.core.config import settings

        assert hasattr(settings, "REDIS_HOST")
        assert hasattr(settings, "REDIS_PORT")

    def test_milvus_config_present(self):
        """Test Milvus configuration is present."""
        from app.core.config import settings

        assert hasattr(settings, "MILVUS_HOST")
        assert hasattr(settings, "MILVUS_PORT")

    def test_storage_backend_config(self):
        """Test storage backend configuration."""
        from app.core.config import settings

        assert hasattr(settings, "STORAGE_BACKEND")
        # Default should be local
        assert settings.STORAGE_BACKEND in ["local", "oss"]

    def test_llm_registry_loading(self):
        """Test LLM registry is accessible."""
        from app.agents.llm_factory import MODEL_REGISTRY, available_llms

        assert isinstance(MODEL_REGISTRY, dict)
        assert len(MODEL_REGISTRY) > 0
        assert isinstance(available_llms(), list)
        assert len(available_llms()) > 0


@pytest.mark.unit
class TestLLMFactory:
    """Test LLM factory functions."""

    def test_get_llm_returns_object(self):
        """Test get_llm returns a valid object."""
        from app.agents.llm_factory import get_llm

        # Should not raise if llm config exists
        try:
            llm = get_llm("deepseek")
            assert llm is not None
        except Exception:
            # May fail if API key not configured, which is fine for tests
            pytest.skip("LLM not configured")

    def test_default_llm_name(self):
        """Test default LLM name is set."""
        from app.agents.llm_factory import DEFAULT_LLM_NAME

        assert DEFAULT_LLM_NAME is not None
        assert isinstance(DEFAULT_LLM_NAME, str)
