# Requirements Agent

Gestión de **proyectos y requerimientos** en lenguaje natural, con un agente que usa el [Model Context Protocol (MCP)](https://modelcontextprotocol.io), una API REST sobre **PostgreSQL**, y un microservicio de **transcripción de voz (Whisper)**.

Administra proyectos y sus requerimientos desde un dashboard React **o** desde el agente conversacional. El LLM elige las herramientas MCP a partir de tu mensaje — sin keyword matching.

## Arquitectura

```
┌───────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                              :5173    │
│  · Dashboard de proyectos + requerimientos                     │
│  · Burbuja de agente (chat + flujo MCP en vivo)                │
│  · Login JWT                                                   │
└───────────────┬─────────────────────────┬─────────────────────┘
                │ HTTP (Bearer)            │ HTTP (Bearer, SSE)
                ▼                          ▼
┌───────────────────────┐     ┌──────────────────────────────┐
│  Backend (FastAPI)    │     │  Agent (FastAPI)        :8001  │
│  :8000                │     │  · LLM (Ollama/OpenAI/        │
│  · Auth JWT           │◄────│    Anthropic)                 │
│  · CRUD proyectos,    │ HTTP│  · Lanza MCP por request      │
│    requerimientos,    │     │  · Propaga el token al MCP    │
│    comments,          │     └──────────────┬───────────────┘
│    transcripciones    │                    │ stdio (MCP)
│  · Solo esto toca BD  │                    ▼
└───────────┬───────────┘         ┌──────────────────────┐
            │                     │  MCP Server          │
            ▼                     │  · Tools proyectos/  │
     ┌─────────────┐              │    requerimientos    │
     │ PostgreSQL  │              └──────────────────────┘
     │ (Docker)    │
     └─────────────┘

┌──────────────────────────────┐
│  STT Service (FastAPI)  :8002 │  mlx-whisper (Apple Silicon)
│  · POST /transcribe (audio)   │  devuelve texto → transcripciones
└──────────────────────────────┘
```

**Regla:** solo el backend toca la base de datos. El MCP llama a la API REST. El token JWT viaja `frontend → agent → MCP → backend`.

## Stack

| Capa | Tecnología | Puerto |
|------|-----------|--------|
| Frontend | React 18, TypeScript, Vite 6 | `5173` |
| Backend | FastAPI, SQLAlchemy 2, Pydantic, PyJWT, bcrypt | `8000` |
| Base de datos | PostgreSQL 16 (psycopg 3) | `5432` |
| Agent | FastAPI, OpenAI/Anthropic SDK | `8001` |
| MCP Server | Python MCP SDK, httpx | stdio |
| STT Service | FastAPI, mlx-whisper | `8002` |
| LLM (default) | [Ollama](https://ollama.com) `qwen2:7b` | `11434` |

## Modelo de datos

- **usuarios** — `username`, `pass_hash` (bcrypt), `status`
- **proyectos** — `usuario_id` (dueño), `name`, `descripcion`, `init_date`, `end_date`
- **requerimientos** — `project_id`, `name`, `descripcion`, `prioridad` (1–5), `estado` (`pendiente`/`en_progreso`/`completado`/`descartado`), `transcripcion_id`
- **transcripciones** — `usuario_id`, `project_id`, `audio_path`, `texto_stt`, `respuesta_llm` (jsonb), `modelo_stt`, `modelo_llm`, `tool_calls` (jsonb)
- **comments** — `requerimiento_id` (1-a-muchos, cascade), `usuario_id`, `description`

Cada proyecto pertenece a un usuario; los endpoints filtran por dueño.

## Quick start

### 1. Base de datos (Docker)

```bash
docker compose up -d db     # PostgreSQL en :5432
```

> Sin Docker, cualquier PostgreSQL sirve — apunta `DATABASE_URL` a él.

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Crea las tablas al arrancar y siembra el admin (`admin` / `admin123`). Docs: http://localhost:8000/docs

### 3. MCP + Agent

```bash
cd mcp-server && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env
cd ../agent && source ../mcp-server/.venv/bin/activate && pip install -r requirements.txt && cp .env.example .env
python agent.py     # :8001
```

### 4. Frontend

```bash
cd frontend && npm install && cp .env.example .env && npm run dev   # :5173
```

### 5. STT Service (opcional, Apple Silicon)

```bash
cd stt-service && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8002
```

### Todo con Docker

```bash
docker compose up   # db + backend
```

## API — Backend (`:8000`)

Todos los endpoints (salvo `/auth/login` y `/health`) requieren `Authorization: Bearer <token>`.

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/auth/login` | Login → JWT |
| `GET` | `/auth/me` | Usuario actual |
| `POST/GET` | `/proyectos` | Crear / listar proyectos |
| `GET/PUT/DELETE` | `/proyectos/{id}` | Ver / actualizar / eliminar |
| `POST/GET` | `/proyectos/{id}/requerimientos` | Crear / listar requerimientos |
| `GET/PUT/DELETE` | `/requerimientos/{id}` | Ver / actualizar / eliminar |
| `POST/GET` | `/requerimientos/{id}/comments` | Crear / listar comentarios |
| `DELETE` | `/comments/{id}` | Eliminar comentario |
| `POST/GET` | `/transcripciones` | Crear / listar transcripciones |
| `GET` | `/transcripciones/{id}` | Ver transcripción |

## Herramientas MCP

`crear_proyecto`, `listar_proyectos`, `obtener_proyecto`, `actualizar_proyecto`, `eliminar_proyecto`, `crear_requerimiento`, `listar_requerimientos`, `actualizar_requerimiento`, `eliminar_requerimiento`.

## Variables de entorno (backend)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://ania:ania@localhost:5432/requirements_agent` | Conexión a Postgres |
| `CORS_ORIGINS` | `http://localhost:5173` | Origen permitido |
| `JWT_SECRET` | — | Secreto para firmar tokens (cámbialo en prod) |
| `JWT_EXPIRE_MINUTES` | `1440` | Expiración del token |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `admin123` | Usuario sembrado al arrancar |

El agente propaga el token del usuario al MCP vía `API_AUTH_TOKEN`, y el MCP lo manda como Bearer al backend.

## Ejemplos de prompts

- "Crea un proyecto llamado Portal Clientes"
- "Muéstrame todos mis proyectos"
- "En el proyecto 2, crea un requerimiento de prioridad 1 llamado Login seguro"
- "Marca como completado el requerimiento 3"

## Licencia

MIT — úsalo libremente para aprender y hacer demos.
