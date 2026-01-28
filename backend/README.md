# ArmorIQ Agent Backend

FastAPI backend with LangChain, LangGraph, and ArmorIQ SDK integration.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- PostgreSQL database

## Quick Start with uv

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and navigate to backend
cd armoriq-agent/backend

# Install all dependencies (creates .venv automatically)
uv sync

# Copy environment file and configure
cp .env.example .env
# Edit .env with your database credentials and API keys

# Run database migrations
uv run alembic upgrade head

# Start the development server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

Key variables in `.env`:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (use `postgresql+asyncpg://...`) |
| `JWT_SECRET` | Secret key for JWT tokens |
| `ARMORIQ_API_KEY` | ArmorIQ SDK API key (starts with `ak_live_` or `ak_test_`) |
| `ARMORIQ_PROXY_URL` | ArmorIQ proxy URL (default: `https://customer-proxy.armoriq.ai`) |

## Running the Server

### Development (with hot reload)
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker Compose
```bash
docker-compose up backend
```

## Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Project Structure

```
backend/
├── app/
│   ├── api/           # API routes
│   ├── config/        # Configuration and constants
│   ├── db/            # Database session management
│   ├── models/        # SQLAlchemy models and Pydantic schemas
│   ├── services/      # Business logic (ArmorIQ, LLM, MCP)
│   ├── utils/         # Utility functions (encryption, etc.)
│   └── main.py        # FastAPI application
├── migrations/        # Alembic migrations
├── scripts/           # Utility scripts
├── pyproject.toml     # Project dependencies
└── .env               # Environment variables
```
