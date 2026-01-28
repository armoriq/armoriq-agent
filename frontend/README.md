# ArmorIQ Agent Frontend

Next.js frontend with shadcn/ui components.

## Prerequisites

- Node.js 20+
- [pnpm](https://pnpm.io/) - Fast package manager

## Setup

```bash
# Install pnpm if not already installed
npm install -g pnpm

# Install dependencies
pnpm install
```

## Environment Setup

```bash
cp .env.local.example .env.local
# Edit .env.local with your configuration
```

## Development

```bash
pnpm dev
```

Open http://localhost:3000

## Build

```bash
pnpm build
pnpm start
```

## Features

- Chat interface with SSE streaming
- Model selector (OpenAI, Anthropic, Google, Mistral, Ollama)
- LLM provider configuration
- MCP server management
- ArmorIQ intent plans viewer
