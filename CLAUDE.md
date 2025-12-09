# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ApplyBot is an automated job application system for hh.ru (HeadHunter) with AI-powered cover letter generation. It's a FastAPI-based async application that uses Ollama (qwen3:14b) for local content generation, SQLAlchemy 2.0 for database operations, and APScheduler for automated daily applications.

## Development Commands

### Docker Development (Recommended)
```bash
docker compose up -d                    # Start all services
docker compose logs -f app              # View logs
docker compose up -d --build            # Rebuild after changes
docker compose up db redis -d           # Start only DB/Redis for local dev
```

### Local Development
```bash
poetry install                          # Install dependencies
poetry shell                            # Activate virtual environment
alembic upgrade head                    # Run migrations
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Migrations
```bash
alembic revision --autogenerate -m "Description"   # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback one
```

### Testing
```bash
poetry run pytest                                  # Run all tests
poetry run pytest --cov=app --cov-report=html     # With coverage
poetry run pytest tests/test_filters.py -v        # Single file
poetry run pytest -k "test_cover_letter"          # By pattern
```

### Code Quality
```bash
poetry run ruff check app/ tests/                 # Lint
poetry run ruff check --fix app/ tests/           # Auto-fix
poetry run ruff format app/ tests/                # Format
poetry run mypy app                               # Type check
poetry run pre-commit run --all-files             # All checks
```

## Architecture

### Core Flow
1. **Authentication**: OAuth flow with HH.ru API, tokens stored in PostgreSQL
2. **Vacancy Search**: HH.ru API with server-side filtering (experience, salary, remote)
3. **Content Generation**: LLM generates cover letters and screening question answers
4. **Application Submission**: Bulk application with duplicate prevention and rate limiting
5. **Scheduling**: APScheduler for automated daily applications

### Key Components

#### Service Layer (`app/services/`)
- **ApplicationService** (`application_service.py`): Core business logic - single/bulk applications, duplicate prevention, filter integration
- **HHClient** (`hh_client.py`): HH.ru API client - OAuth, vacancy search, application submission with rate limiting
- **PromptBuilder** (`prompt_builder.py`): Constructs prompts for LLM cover letter/answer generation
- **LLM Providers** (`services/llm/`): Abstract base with factory pattern for provider selection

#### Database Layer
- **SQLAlchemy 2.0** async via `asyncpg`
- **Models**: `Token` (OAuth), `ApplicationHistory` (tracking), `SchedulerConfig` (scheduler settings)
- **Storage** (`app/core/storage.py`): `TokenStorage` utility, `async_session` factory

#### Router Layer (`app/routers/`)
- `auth.py`: OAuth login/callback, resume selection
- `apply.py`: Single application endpoint
- `hh_apply.py`: Bulk application with cancellation support
- `scheduler.py`: CRUD for scheduled jobs

#### Filtering System (`app/utils/filters.py`)
- **ApplicationFilter**: Client-side filtering (company exclusions, employment type, schedule, experience)

### Duplicate Prevention
Applications skipped if:
1. Already applied per HH.ru API (`GET /negotiations`)
2. Already in local `ApplicationHistory` table
3. Vacancy has `relations` containing "got_response" or "response"
4. Vacancy is archived

### Language Detection
LLM base class detects language via Cyrillic character ratio (>30% = Russian). Cover letters match vacancy language.

## Important Implementation Details

### Async Pattern
All database and external API calls use async/await:
```python
async with async_session() as session:
    result = await session.execute(query)
    await session.commit()
```

### Dependency Injection
```python
from app.services.llm.dependencies import get_llm_provider
async def endpoint(llm_provider: LLMProvider = Depends(get_llm_provider)):
    ...
```

### Error Handling
- HH.ru API errors returned in `ApplyResponse` with status="error"
- Rate limiting (429) handled by HHClient with exponential backoff

### Testing
- Fixtures in `tests/conftest.py` (mock HH client, LLM provider, DB session)
- SQLite for tests (via `aiosqlite`)
- Coverage excludes: `tasks.py`, `hh_client.py`, `scheduler_service.py`, `providers.py` (external integrations)

### Scheduler
- APScheduler `AsyncIOScheduler` with jobs stored in `SchedulerConfig`
- Timezone-aware (default: Europe/Moscow)
- Started/stopped via application lifespan

## Migration Notes
1. Import all models in `app/core/storage.py` to register with Base
2. Alembic uses sync driver (psycopg2), app uses async (asyncpg)
3. Review autogenerated migrations before applying

## Environment Variables
See `.env.example`. Key variables:
- `HH_CLIENT_ID`, `HH_CLIENT_SECRET`: HH.ru OAuth credentials
- `OLLAMA_BASE_URL`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model to use (default: qwen3:14b)
- `DATABASE_URL`: PostgreSQL (use `postgresql+asyncpg://` for async)
- `SCHEDULER_ENABLED`, `SCHEDULER_AUTO_START`: Scheduler control
