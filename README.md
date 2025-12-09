# ApplyBot 🤖

[![CI](https://github.com/FrostWillmott/ApplyBot/actions/workflows/ci.yml/badge.svg)](https://github.com/FrostWillmott/ApplyBot/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automated job application system for hh.ru with AI-powered cover letter generation.

## 🚧 Project Status

**🟢 Working** (Last update: December 2025)

### ✅ Features
- OAuth authentication with hh.ru
- Resume selection from HH.ru profile
- Vacancy search with API-level filtering (experience, salary, remote)
- **AI Assistant** (Ollama qwen3:14b):
  - Cover letter generation with real candidate data (name, email)
  - Screening questions answering
  - Auto language detection (RU/EN based on vacancy)
- Skip already applied vacancies (fetched from HH.ru API)
- **Real-time bulk applications** with Server-Sent Events (SSE):
  - Live progress updates during application process
  - Instant counter updates on each successful application
  - Results displayed as they arrive
  - No timeout issues with long-running operations
- **Scheduler** for automated daily applications
- Daily application counter (200 limit with hard block)
- Completion notifications (sound + browser)
- Rate limiting protection (429 handling)
- FastAPI + SQLAlchemy async architecture
- Docker development environment with Ollama on host

### 🔄 Duplicate Prevention

Before sending applications, the system:
1. Fetches all your existing applications from HH.ru API (`GET /negotiations`)
2. Filters out vacancies you've already applied to
3. Only sends to new vacancies

This prevents wasting daily quota on duplicates.

### 📋 Planned
- Application history dashboard
- Response tracking from employers

## 🛠️ Tech Stack

### Backend
- **FastAPI** 0.123+ - async web framework
- **SQLAlchemy 2.0** - ORM with async support
- **PostgreSQL** - main database
- **asyncpg** - async PostgreSQL driver
- **Alembic** - database migrations
- **Redis** + **RQ** - task queue
- **APScheduler** - job scheduling
- **sse-starlette** - Server-Sent Events for real-time updates

### AI/ML
- **Ollama** (qwen3:14b) - local text generation

### Development
- **Poetry** - dependency management
- **Docker** + **Docker Compose** - containerization
- **Ruff** - linting and formatting
- **MyPy** - static type checking

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Docker and Docker Compose
- hh.ru developer account
- Ollama installed and running locally

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/FrostWillmott/ApplyBot.git
cd ApplyBot
```

2. **Create `.env` file from example**
```bash
cp .env.example .env
```

Then edit `.env` and fill in your credentials:

| Variable | Description | Where to get |
|----------|-------------|--------------|
| `HH_CLIENT_ID` | HeadHunter OAuth Client ID | [dev.hh.ru/admin](https://dev.hh.ru/admin) |
| `HH_CLIENT_SECRET` | HeadHunter OAuth Secret | [dev.hh.ru/admin](https://dev.hh.ru/admin) |
| `OLLAMA_BASE_URL` | Ollama server URL | Default: http://host.docker.internal:11434 (for Docker) |
| `OLLAMA_MODEL` | Model name | Default: qwen3:14b |
| `POSTGRES_PASSWORD` | Database password | Set your own secure password |

Other variables have sensible defaults for Docker setup.

3. **Start the application**
```bash
docker compose up -d

# View logs
docker compose logs -f app
```

Application available at `http://localhost:8000`

### Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend (nginx) | 8000 | Web interface |
| Backend (FastAPI) | 8001 | API server |
| PostgreSQL | 5434 | Database |
| Redis | 6380 | Task queue |

### Local Development (without Docker)

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Start PostgreSQL and Redis
docker compose up db redis -d

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Usage

### 1. Authentication

Go to `http://localhost:8000` and click "Login with HeadHunter".

### 2. API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 3. Bulk Applications

**Regular Endpoint** (waits for all applications to complete):
```bash
POST /apply/bulk?max_applications=20
Content-Type: application/json

{
  "position": "Python Developer",
  "resume": "Experienced Python developer...",
  "skills": "Python, FastAPI, PostgreSQL",
  "experience": "5+ years",
  "resume_id": "your_resume_id",
  "exclude_companies": ["CompanyToExclude"],
  "salary_min": 100000,
  "remote_only": true,
  "use_cover_letter": true
}
```

**Streaming Endpoint** (real-time progress via SSE):
```bash
POST /apply/bulk/stream?max_applications=20
Accept: text/event-stream

# Returns Server-Sent Events with progress updates:
# event: start
# data: {"event":"start","current":0,"total":20,"message":"Starting..."}
#
# event: progress
# data: {"event":"progress","current":1,"total":20,"success_count":1,...}
#
# event: complete
# data: {"event":"complete","current":20,"total":20,"success_count":18,...}
```

### 4. Scheduler

The scheduler allows automated daily applications:
- Configure via web interface or API (`/scheduler/*`)
- Set preferred time, days, and limits
- Automatically runs bulk applications on schedule

## 🤖 AI Assistant

The AI Assistant (powered by Ollama with qwen3:14b model) provides:

### Cover Letter Generation
- Personalized based on vacancy requirements and candidate profile
- **Auto-detects language**: Russian vacancies → Russian letters, English → English
- 300-400 words, professional tone

### Screening Questions
- Automatically answers employer questions
- Uses candidate profile for relevant responses
- Same language as vacancy

### Language Detection
```python
# Checks for Cyrillic characters in vacancy text
is_russian = any(char in text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
```

## ⚙️ Configuration

Frontend configuration is stored in `app/static/config.js`:

### HH.ru API Limits

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MAX_PER_REQUEST` | 50 | Maximum applications per single API request |
| `DAILY_LIMIT` | 200 | Daily limit for applications (approximate) |
| `WARNING_THRESHOLD` | 150 | Counter turns orange when approaching daily limit |
| `MIN_COVER_LETTER_LENGTH` | 50 | Minimum cover letter length required by HH.ru |

### Timing Estimates

| Parameter | Value | Description |
|-----------|-------|-------------|
| `WITH_COVER_LETTER` | 15 sec | Time per application with AI Assistant enabled |
| `WITHOUT_COVER_LETTER` | 2 sec | Time per application without AI Assistant |
| `REQUEST_TIMEOUT` | 600000 ms | Request timeout (10 minutes) |

### Daily Counter

The frontend tracks daily application count in browser localStorage:
- Automatically resets at midnight
- Color changes: green (0-149) → orange (150-199) → red (200+)
- **Hard block at 200**: button disabled, cannot send more applications
- Auto-limits batch size to remaining quota
- Data persists per browser/device

> **Note:** HH.ru limits may vary by account type. Premium accounts may have higher limits.

### Scheduler Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SCHEDULER_DEFAULT_HOUR` | 9 | Default run hour |
| `SCHEDULER_DEFAULT_MINUTE` | 0 | Default run minute |
| `SCHEDULER_DEFAULT_DAYS` | mon-fri | Days to run |
| `SCHEDULER_DEFAULT_TIMEZONE` | Europe/Moscow | Timezone |
| `SCHEDULER_MAX_APPLICATIONS` | 20 | Max applications per run |

## 📁 Project Structure

```
ApplyBot/
├── .github/
│   ├── workflows/         # CI/CD pipelines
│   │   ├── ci.yml         # Lint, test, security scan
│   │   └── cd.yml         # Build & deploy Docker
│   └── dependabot.yml     # Auto-update dependencies
├── app/
│   ├── core/              # Configuration and utilities
│   ├── models/            # SQLAlchemy models
│   ├── routers/           # FastAPI endpoints
│   ├── schemas/           # Pydantic models
│   ├── services/          # Business logic
│   │   └── llm/           # LLM providers (Ollama)
│   ├── static/            # Web interface
│   │   ├── config.js      # Frontend configuration
│   │   ├── script.js      # Main JavaScript
│   │   ├── styles.css     # Styles
│   │   └── index.html     # Main page
│   ├── utils/             # Utilities
│   ├── tasks.py           # RQ background tasks
│   └── main.py            # Entry point
├── tests/                 # Test suite (pytest)
├── alembic/               # Database migrations
├── docker-compose.yml     # Docker configuration
├── Dockerfile             # Application image
├── Dockerfile.frontend    # Nginx frontend
├── pyproject.toml         # Dependencies (Poetry)
├── ruff.toml              # Linter configuration
├── .env.example           # Environment template
├── .pre-commit-config.yaml # Pre-commit hooks
└── README.md
```

## 🔧 Development

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/test_filters.py -v
```

Current coverage: **72%** (239 tests)

### Code Quality
```bash
# Lint
poetry run ruff check app/ tests/

# Auto-fix
poetry run ruff check --fix app/ tests/

# Format
poetry run ruff format app/ tests/

# Type check
poetry run mypy app
```

### Pre-commit Hooks
```bash
# Install hooks
poetry run pre-commit install

# Run manually
poetry run pre-commit run --all-files
```

## 🙏 Acknowledgments

- [HeadHunter API](https://dev.hh.ru/)
- [Ollama](https://ollama.ai/)
- [FastAPI](https://fastapi.tiangolo.com/)

---

<sub>⚠️ **Disclaimer:** Project in development. Use at your own risk.</sub>
