# AI Project Manager POC

A minimal monorepo that demonstrates **natural-language project management** using an AI agent, the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), and a REST API.

Manage projects from a React dashboard **or** from a floating agent chat. The LLM chooses MCP tools from your message — no keyword matching, no hardcoded intents.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                         :5173      │
│  · Projects dashboard (manual CRUD)                         │
│  · Floating agent bubble (chat + live MCP flow)             │
└───────────────┬─────────────────────────┬───────────────────┘
                │ HTTP                    │ HTTP (SSE stream)
                ▼                         ▼
┌───────────────────────┐     ┌─────────────────────────────┐
│  Backend (FastAPI)    │     │  Agent (FastAPI)       :8001  │
│  :8000                │     │  · LLM (Ollama/OpenAI/       │
│  · CRUD /projects     │◄────│    Anthropic)               │
│  · SQLite only here   │ HTTP│  · Spawns MCP subprocess    │
└───────────┬───────────┘     └──────────────┬──────────────┘
            │                                 │ stdio (MCP)
            ▼                                 ▼
     ┌─────────────┐               ┌─────────────────────┐
     │   SQLite    │               │  MCP Server         │
     │ projects.db │               │  · 5 project tools  │
     └─────────────┘               └─────────────────────┘
```

**Rule:** Only the backend touches the database. The MCP server calls the REST API. The agent talks to the LLM and MCP.

## Stack

| Layer | Tech | Port |
|-------|------|------|
| Frontend | React 18, TypeScript, Vite 6 | `5173` |
| Backend | FastAPI, SQLAlchemy, Pydantic | `8000` |
| Database | SQLite | — |
| Agent | FastAPI, OpenAI SDK, Anthropic SDK | `8001` |
| MCP Server | Python MCP SDK, httpx | stdio |
| LLM (default) | [Ollama](https://ollama.com) — local, no API key | `11434` |

## Folder structure

```
ai-project-agent-poc/
├── README.md
├── .gitignore
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   └── components/
│   │       ├── ProjectsDashboard.tsx   # manual CRUD
│   │       ├── AgentBubble.tsx         # floating chat
│   │       └── McpFlowPanel.tsx        # live MCP pipeline UI
│   └── .env.example
├── backend/
│   └── app/
│       ├── main.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       └── routers/projects.py
├── mcp-server/
│   └── server.py                       # MCP tools → REST API
└── agent/
    └── agent.py                        # LLM + MCP orchestration
```

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **[Ollama](https://ollama.com)** (recommended — free, local) **or** an OpenAI / Anthropic API key

```bash
ollama pull qwen2:7b
ollama serve   # if not already running
```

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 2. MCP Server dependencies

The MCP server runs as a **subprocess** of the agent (stdio). Install deps once:

```bash
cd mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Agent

```bash
cd agent
source ../mcp-server/.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python agent.py
```

Agent: **http://localhost:8001** · Docs: **http://localhost:8001/docs**

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open **http://localhost:5173**

## Run all services (3 terminals)

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 2 — Agent (spawns MCP automatically)
cd agent && source ../mcp-server/.venv/bin/activate && python agent.py

# Terminal 3 — Frontend
cd frontend && npm run dev
```

## How the agent works

1. You send a message from the chat bubble.
2. The agent starts the MCP server as a subprocess and lists available tools.
3. Your message + tool schemas go to the LLM (Ollama by default).
4. The model **reasons** and may call tools like `create_project` or `list_projects`.
5. The agent executes each tool via MCP → HTTP → SQLite.
6. The model replies with a short confirmation.
7. The UI streams events (`mcp_spawn`, `tool_start`, `message`, …) in the MCP flow panel.

No `if "create" in message` logic — tool selection is entirely up to the LLM.

## Environment variables

| Service | Variable | Default | Description |
|---------|----------|---------|-------------|
| Backend | `DATABASE_URL` | `sqlite:///./projects.db` | SQLite connection |
| Backend | `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origin |
| MCP | `API_BASE_URL` | `http://localhost:8000` | FastAPI base URL |
| Agent | `AI_PROVIDER` | `ollama` | `ollama`, `openai`, or `anthropic` |
| Agent | `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible API |
| Agent | `OLLAMA_MODEL` | `qwen2:7b` | Local model name |
| Agent | `OPENAI_API_KEY` | — | Required when `AI_PROVIDER=openai` |
| Agent | `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| Agent | `ANTHROPIC_API_KEY` | — | Required when `AI_PROVIDER=anthropic` |
| Agent | `ANTHROPIC_MODEL` | `claude-3-5-haiku-latest` | Anthropic model |
| Agent | `AGENT_PORT` | `8001` | Agent HTTP port |
| Agent | `MCP_SERVER_SCRIPT` | `../mcp-server/server.py` | Path to MCP server |
| Frontend | `VITE_API_URL` | `http://localhost:8000` | Backend URL |
| Frontend | `VITE_AGENT_URL` | `http://localhost:8001` | Agent URL |

## API — Backend (`:8000`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/projects` | Create project |
| `GET` | `/projects` | List projects |
| `GET` | `/projects/{id}` | Get project |
| `PUT` | `/projects/{id}` | Update project |
| `DELETE` | `/projects/{id}` | Delete project |
| `GET` | `/health` | Health check |

**Project fields:** `id`, `name`, `description`, `status`, `created_at`, `updated_at`

**Statuses:** `active`, `completed`, `archived`, `on_hold`

## API — Agent (`:8001`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Chat (JSON response) |
| `POST` | `/chat/stream` | Chat with SSE events (used by UI) |
| `GET` | `/health` | Provider + model info |

## MCP tools

| Tool | REST mapping |
|------|----------------|
| `create_project` | `POST /projects` |
| `list_projects` | `GET /projects` |
| `get_project` | `GET /projects/{id}` |
| `update_project` | `PUT /projects/{id}` |
| `delete_project` | `DELETE /projects/{id}` |

## Example prompts

- "Create a project called Bitcoin Zone"
- "Show me all my projects"
- "Change Bitcoin Zone status to completed"
- "Delete project #3"

## Health checks

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

## Switching LLM provider

Edit `agent/.env`:

```env
# Ollama (default)
AI_PROVIDER=ollama
OLLAMA_MODEL=qwen2:7b

# OpenAI
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Anthropic
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Restart the agent after changing provider.

## License

MIT — use freely for learning and demos.
