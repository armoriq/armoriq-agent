# ArmorIQ Agent

Multi-LLM Chatbot Agent Platform with MCP Integration and ArmorIQ SDK.

## Features

- **Multi-LLM Support**: OpenAI, Anthropic, Google, Mistral, Ollama, OpenRouter
- **MCP Integration**: Dynamic tool connections with connection pooling
- **ArmorIQ SDK**: Plan capture and verified tool execution
- **SSE Streaming**: Real-time chat responses
- **Modern Stack**: FastAPI (Python) + Next.js (TypeScript)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Or for local development:
  - Python 3.11+ with [uv](https://github.com/astral-sh/uv)
  - Node.js 20+ with [pnpm](https://pnpm.io/)
  - PostgreSQL

### With Docker (Recommended)

```bash
# Clone and configure
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
# Edit .env files with your API keys

# Start all services
docker-compose up -d
```

### Local Development

**Backend:**
```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
pnpm install
pnpm dev
```

## URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

```
armoriq-agent/
├── backend/          # FastAPI + LangChain + ArmorIQ
├── frontend/         # Next.js + shadcn/ui
└── docker-compose.yml
```

## License

MIT
