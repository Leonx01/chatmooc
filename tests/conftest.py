"""Test configuration and shared fixtures for ChatMooc."""
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Environment Configuration
# ============================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    # Use .env values if available, else fallback to docker-compose defaults
    test_env = {
        # Use chatmooc_dev database (from docker-compose)
        "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE", "chatmooc"),
        "MYSQL_USER": os.getenv("MYSQL_USER", "root"),
        "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD", "chatmooc"),
        "MYSQL_HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "MYSQL_PORT": os.getenv("MYSQL_PORT", "3308"),
        # Redis
        "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "REDIS_HOST": os.getenv("REDIS_HOST", "127.0.0.1"),
        "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
        "REDIS_DB": "0",  # Use default DB
        # Milvus
        "MILVUS_HOST": os.getenv("MILVUS_HOST", "127.0.0.1"),
        "MILVUS_PORT": "19530",
        # API
        "APP_NAME": "chatmooc_test",
        "API_V1_PREFIX": "/api/v1",
        # LLM (use dummy for unit tests)
        "LLM_NAME": "deepseek",
        "DEEPSEEK_API_KEY": "sk-test-dummy-key-for-testing",
        # Disable external services
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        # Storage
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": str(PROJECT_ROOT / "volumes" / "test_uploads"),
        "LOCAL_PARSED_DIR": str(PROJECT_ROOT / "volumes" / "test_parsed"),
    }

    # Save original env
    original_env = os.environ.copy()

    # Apply test env
    os.environ.update(test_env)

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


# ============================================================
# Application Fixtures
# ============================================================


@pytest.fixture(scope="session")
def mock_redis():
    """Mock Redis client for unit tests."""
    with patch("app.core.redis_core.redis_client") as mock:
        client = MagicMock()
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=1)
        client.exists = AsyncMock(return_value=0)
        client.ping = AsyncMock(return_value=True)
        mock.client = client
        yield mock


@pytest.fixture(scope="session")
def mock_milvus():
    """Mock Milvus client for unit tests."""
    with patch("app.core.milvus_core.MilvusClient") as mock:
        client = MagicMock()
        client.query = AsyncMock(return_value=[])
        client.insert = AsyncMock(return_value={"insert_count": 1})
        client.delete = AsyncMock(return_value={"delete_count": 1})
        client.search = AsyncMock(return_value=[[]])
        mock.return_value = client
        yield mock


@pytest.fixture(scope="session")
def mock_llm():
    """Mock LLM factory for unit tests."""
    with patch("app.agents.llm_factory.get_llm") as mock:
        # Create a mock LLM that returns empty responses
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="Mocked LLM response")
        )
        mock_llm.with_config = MagicMock(return_value=mock_llm)
        mock.return_value = mock_llm
        yield mock


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    with patch("app.core.mysql_core.get_session") as mock:
        session = MagicMock()
        mock.return_value = session
        yield session


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Create a test client for the FastAPI application.

    Note: This fixture requires the app to be importable.
    For full integration tests, use the app with all dependencies.
    For unit tests, prefer mocking individual components.
    """
    try:
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client
    except Exception as e:
        pytest.skip(f"Cannot create test client: {e}")


# ============================================================
# Authentication Fixtures
# ============================================================


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    from app.models import Users

    user = MagicMock(spec=Users)
    user.uid = 1
    user.uname = "testuser"
    user.created_at = None
    user.updated_at = None
    return user


@pytest.fixture
def auth_headers(mock_user) -> dict:
    """Generate authentication headers for API requests."""
    # Generate a mock JWT token (for testing purposes)
    # In real tests, use proper JWT generation
    with patch("app.api.v1.routes.auth.get_current_user", return_value=mock_user):
        # This fixture should be used with client fixture
        yield {"Authorization": "Bearer mock-token"}


# ============================================================
# Test Data Fixtures - Database Seeding
# ============================================================


@pytest.fixture(scope="session")
def db_session():
    """
    Get database session for test data seeding.
    This connects to the actual database (chatmooc).
    """
    try:
        from app.core.mysql_core import get_session
        from sqlalchemy import text

        # Test connection
        import asyncio

        async def _get_session():
            async for session in get_session():
                # Test basic query
                await session.execute(text("SELECT 1"))
                return session

        return asyncio.run(_get_session())
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
def test_user(db_session):
    """
    Create a test user in the database.
    Returns the user object with uid.
    """
    import uuid
    from datetime import datetime
    from sqlalchemy import text

    user_id = f"test_{uuid.uuid4().hex[:8]}"
    now = datetime.now()

    try:
        db_session.execute(
            text("""
                INSERT INTO users (uid, uname, created_at, updated_at)
                VALUES (:uid, :uname, :created_at, :updated_at)
                ON DUPLICATE KEY UPDATE uname = uname
            """),
            {
                "uid": user_id,
                "uname": f"testuser_{user_id[:6]}",
                "created_at": now,
                "updated_at": now,
            }
        )
        db_session.commit()

        # Fetch the user
        result = db_session.execute(
            text("SELECT uid, uname FROM users WHERE uid = :uid"),
            {"uid": user_id}
        )
        row = result.fetchone()

        class User:
            def __init__(self, uid, uname):
                self.uid = uid
                self.uname = uname

        yield User(row[0], row[1])

        # Cleanup - delete after test
        try:
            db_session.execute(text("DELETE FROM users WHERE uid = :uid"), {"uid": user_id})
            db_session.commit()
        except:
            pass

    except Exception as e:
        pytest.skip(f"Cannot create test user: {e}")


@pytest.fixture
def test_resource(db_session, test_user):
    """
    Create a test resource in the database.
    Returns the resource with rid.
    """
    import uuid
    from datetime import datetime
    from sqlalchemy import text

    resource_id = str(uuid.uuid4())
    now = datetime.now()

    try:
        db_session.execute(
            text("""
                INSERT INTO resources (rid, uid, url, rname, rtype, created_at, updated_at)
                VALUES (:rid, :uid, :url, :rname, :rtype, :created_at, :updated_at)
                ON DUPLICATE KEY UPDATE rname = rname
            """),
            {
                "rid": resource_id,
                "uid": test_user.uid,
                "url": f"http://example.com/test_{resource_id}.pdf",
                "rname": f"test_resource_{resource_id[:6]}.pdf",
                "rtype": "pdf",
                "created_at": now,
                "updated_at": now,
            }
        )
        db_session.commit()

        class Resource:
            def __init__(self, rid, uid, rname, rtype):
                self.rid = rid
                self.uid = uid
                self.rname = rname
                self.rtype = rtype

        yield Resource(resource_id, test_user.uid, f"test.pdf", "pdf")

        # Cleanup
        try:
            db_session.execute(text("DELETE FROM resources WHERE rid = :rid"), {"rid": resource_id})
            db_session.commit()
        except:
            pass

    except Exception as e:
        pytest.skip(f"Cannot create test resource: {e}")


@pytest.fixture
def test_unit(db_session, test_user):
    """Create a test learning unit."""
    import uuid
    from datetime import datetime
    from sqlalchemy import text

    unit_id = f"unit_{uuid.uuid4().hex[:8]}"
    now = datetime.now()

    try:
        db_session.execute(
            text("""
                INSERT INTO units (unit_id, pid, uid, goal, guide, created_at)
                VALUES (:unit_id, :pid, :uid, :goal, :guide, :created_at)
                ON DUPLICATE KEY UPDATE goal = goal
            """),
            {
                "unit_id": unit_id,
                "pid": "default_path",  # Use a default path
                "uid": test_user.uid,
                "goal": "Learn Python basics",
                "guide": "# Python Basics\n- Variables\n- Functions",
                "created_at": now,
            }
        )
        db_session.commit()

        class Unit:
            def __init__(self, unit_id, uid, goal):
                self.unit_id = unit_id
                self.uid = uid
                self.goal = goal

        yield Unit(unit_id, test_user.uid, "Learn Python basics")

        # Cleanup
        try:
            db_session.execute(text("DELETE FROM units WHERE unit_id = :unit_id"), {"unit_id": unit_id})
            db_session.commit()
        except:
            pass

    except Exception as e:
        pytest.skip(f"Cannot create test unit: {e}")


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user registration data."""
    return {
        "username": "testuser",
        "password": "TestPassword123!",
    }


@pytest.fixture
def sample_resource_data() -> dict:
    """Sample resource upload data."""
    return {
        "rname": "test_document.pdf",
        "rtype": "pdf",
    }


@pytest.fixture
def sample_chat_message() -> dict:
    """Sample chat message data."""
    return {
        "message": "What is Python?",
        "unit_id": "unit-123",
        "resource_ids": ["res-123"],
    }


# ============================================================
# Cleanup Fixtures
# ============================================================


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Clean up test files after each test."""
    yield
    # Cleanup is handled by separate cleanup tests or CI pipeline


# ============================================================
# Mock External Services
# ============================================================


@pytest.fixture
def mock_celery():
    """Mock Celery app for unit tests."""
    with patch("app.core.celery_core.celery_app") as mock:
        mock.send_task = MagicMock()
        mock.connection_for_write = MagicMock()
        yield mock


@pytest.fixture
def mock_storage():
    """Mock storage backend for unit tests."""
    with patch("app.core.storage.resolve_local_storage_dir") as mock:
        mock.return_value = PROJECT_ROOT / "volumes" / "test_uploads"
        yield mock
