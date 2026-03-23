# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChatMooc is an AI-powered tutoring platform that uses LangGraph agents to provide personalized learning experiences. Users can upload learning resources (PDFs, documents, videos), and the AI tutor generates learning paths, flashcards, and exercises.

## Commands

```bash
# Start all infrastructure services (MySQL, Redis, Milvus, RabbitMQ, Ollama)
docker compose up -d

# Run the FastAPI application
uvicorn app.main:app --reload --port 8000

# Run Celery worker for async tasks
celery -A app.core.celery_core worker --loglevel=info

# Run all tests
pytest

# Run unit tests only (fast, no external services)
pytest tests/ -m unit

# Run integration tests (requires services)
pytest tests/ -m integration

# Run specific test file
pytest tests/test_services/test_config.py -v

# Run langgraph dev (for agent development)
langgraph dev
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Server                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐│
│  │   /auth    │  │  /resources  │  │      /chat/stream       ││
│  │  (JWT auth)│  │  (file upload)│  │   (LangGraph SSE)      ││
│  └─────────────┘  └──────────────┘  └─────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌────────────┐   ┌────────────┐   ┌───────────┐
     │   MySQL    │   │   Redis    │   │  Milvus   │
     │  (users,  │   │  (cache,   │   │ (vector   │
     │ resources)│   │  sessions) │   │  store)   │
     └────────────┘   └────────────┘   └───────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Celery Workers │
                    │ (async parsing) │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │     Ollama      │
                    │ (embeddings)    │
                    └─────────────────┘
```

## Key Components

### Agents (`app/agents/`)
- **tutor_agent.py**: Core LangGraph agent with StateGraph workflow (llm_call → tool_node → loop)
- **planner_agent.py**: Learning path planner
- **tools/**: Agent tools (flashcards, exercises, memo, fetch_info)
- **prompts/**: Agent system prompts (tutor.md, planner.md, etc.)

### API Routes (`app/api/v1/routes/`)
- **auth.py**: JWT authentication
- **resources.py**: File upload/parsing
- **chat.py**: SSE streaming chat endpoint
- **test.py**: Rate limiting test endpoints

### Core Services (`app/core/`)
- **config.py**: Settings via pydantic-settings (loads from .env)
- **mysql_core.py**: SQLAlchemy database
- **redis_core.py**: Redis client
- **milvus_core.py**: Vector database
- **celery_core.py**: Async task queue
- **storage.py**: Local/OSS file storage

## Configuration

Environment variables are defined in `.env` and loaded via `app/core/config.py`. Key settings:
- `LLM_NAME`: Default LLM (deepseek, gpt-4o-mini, claude-3-5-sonnet, ollama)
- Database connection strings
- Redis/Milvus endpoints
- Storage backend (local/oss)

## Database Schema

Key tables: Users, Resources, Sessions, Units, FlashCards, Exercises, MilvusVectors. See `db/schema.md` for full schema.

## Agent Configuration

The tutor agent requires these configurable parameters:
- `user_id`: User identifier
- `unit_id`: Learning unit identifier
- `resource_ids`: List of resource IDs to reference

These are passed via LangGraph's `configurable` field in the chat API.

## Testing

The project has a standalone test framework in `tests/` directory:

### Test Structure
- `tests/conftest.py`: Shared fixtures (test env, mock clients)
- `tests/test_api/`: API endpoint tests
- `tests/test_services/`: Service and model tests

### Test Environment
- `.env.test`: Test-specific environment variables
- Tests use separate test database and Redis DB
- Mock external services (LLM, Milvus, Redis) where needed

### CI/CD
- `.github/workflows/ci.yml`: GitHub Actions workflow
- Runs lint, unit tests, and integration tests
- Uses `docker compose` services for integration tests

### Markers
- `@pytest.mark.unit`: Fast tests, no external dependencies
- `@pytest.mark.integration`: Tests requiring running services
