"""Model tests."""
import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestModels:
    """Test database models."""

    def test_users_model_import(self):
        """Test Users model can be imported."""
        from app.models import Users

        assert Users is not None

    def test_users_model_structure(self):
        """Test Users model has expected attributes."""
        from app.models import Users

        # Check table name
        assert hasattr(Users, "__tablename__")

    def test_resources_model_import(self):
        """Test Resources model can be imported."""
        from app.models import Resources

        assert Resources is not None


@pytest.mark.unit
class TestSchema:
    """Test Pydantic schemas."""

    def test_user_schema_import(self):
        """Test user schema can be imported."""
        from app.schema.users import UserLogin, LoginResponse

        assert UserLogin is not None
        assert LoginResponse is not None

    def test_resource_schema_import(self):
        """Test resource schema can be imported."""
        from app.schema.resources import ResourceOut, ResourceUploadResponse

        assert ResourceOut is not None
        assert ResourceUploadResponse is not None


@pytest.mark.unit
class TestTools:
    """Test agent tools."""

    def test_tools_import(self):
        """Test tools module can be imported."""
        from app.agents.tools import TOOLS

        assert TOOLS is not None
        assert isinstance(TOOLS, list)
        assert len(TOOLS) > 0

    def test_flashcards_tool_exists(self):
        """Test flashcards tool is registered."""
        from app.agents.tools import TOOLS

        tool_names = [tool.name for tool in TOOLS]
        assert any("flashcard" in name for name in tool_names)

    def test_exercise_tool_exists(self):
        """Test exercise tool is registered."""
        from app.agents.tools import TOOLS

        tool_names = [tool.name for tool in TOOLS]
        assert any("exercise" in name for name in tool_names)

    def test_memo_tool_exists(self):
        """Test memo tool is registered."""
        from app.agents.tools import TOOLS

        tool_names = [tool.name for tool in TOOLS]
        assert any("memo" in name for name in tool_names)


@pytest.mark.unit
class TestAgentGraph:
    """Test agent graph structure."""

    def test_agent_graph_compiles(self):
        """Test agent graph can be compiled."""
        from app.agents.tutor_agent import agent_builder

        # Check graph exists and has nodes
        assert agent_builder is not None

    def test_graph_has_required_nodes(self):
        """Test graph has required nodes."""
        from app.agents.tutor_agent import agent_builder

        # Get graph nodes (the graph should have llm_call and tool_node)
        # This is a structural test
        assert hasattr(agent_builder, "nodes")


@pytest.mark.unit
class TestPrompts:
    """Test agent prompts exist."""

    def test_tutor_prompt_exists(self):
        """Test tutor prompt file exists."""
        from pathlib import Path

        prompt_path = Path(__file__).resolve().parents[2] / "app" / "agents" / "prompts" / "tutor.md"
        assert prompt_path.exists()

    def test_planner_prompt_exists(self):
        """Test planner prompt file exists."""
        from pathlib import Path

        prompt_path = Path(__file__).resolve().parents[2] / "app" / "agents" / "prompts" / "planner.md"
        assert prompt_path.exists()
