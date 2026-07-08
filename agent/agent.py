"""AI agent that uses MCP tools (backed by the REST API) to manage projects."""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:7b")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", sys.executable)
MCP_SERVER_SCRIPT = os.getenv(
    "MCP_SERVER_SCRIPT",
    str(Path(__file__).resolve().parent.parent / "mcp-server" / "server.py"),
)

SYSTEM_PROMPT = """Eres un asistente de gestión de proyectos y requerimientos. Ayudas a crear, listar, ver, actualizar y eliminar proyectos, y a gestionar los requerimientos de cada proyecto.

Usa las herramientas disponibles para cumplir las solicitudes. Cuando el usuario se refiera a un proyecto o requerimiento por su nombre, primero lista para encontrar el ID correcto antes de actualizar o eliminar. Para crear un requerimiento necesitas el project_id: si no lo tienes, lista los proyectos primero.

La prioridad de un requerimiento es un entero de 1 (más alta) a 5 (más baja).
Los estados válidos de un requerimiento son: pendiente, en_progreso, completado, descartado.

Después de completar acciones, responde con una confirmación breve y amable (1-2 oraciones). No vuelques JSON crudo a menos que el usuario pida detalles."""

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]

TOOL_HTTP: dict[str, Callable[[dict[str, Any]], tuple[str, str]]] = {
    "crear_proyecto": lambda _: ("POST", "/proyectos"),
    "listar_proyectos": lambda _: ("GET", "/proyectos"),
    "obtener_proyecto": lambda a: ("GET", f"/proyectos/{a.get('id', '?')}"),
    "actualizar_proyecto": lambda a: ("PUT", f"/proyectos/{a.get('id', '?')}"),
    "eliminar_proyecto": lambda a: ("DELETE", f"/proyectos/{a.get('id', '?')}"),
    "crear_requerimiento": lambda a: ("POST", f"/proyectos/{a.get('project_id', '?')}/requerimientos"),
    "listar_requerimientos": lambda a: ("GET", f"/proyectos/{a.get('project_id', '?')}/requerimientos"),
    "actualizar_requerimiento": lambda a: ("PUT", f"/requerimientos/{a.get('id', '?')}"),
    "eliminar_requerimiento": lambda a: ("DELETE", f"/requerimientos/{a.get('id', '?')}"),
}


def _tool_http(name: str, arguments: dict[str, Any]) -> tuple[str, str]:
    mapper = TOOL_HTTP.get(name)
    return mapper(arguments) if mapper else ("?", "?")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


class ToolExecution(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: str


class ChatResponse(BaseModel):
    reply: str
    tool_executions: list[ToolExecution] = Field(default_factory=list)


def _mcp_tool_to_openai(tool: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


def _mcp_tool_to_anthropic(tool: Any) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


def _mcp_server_env(auth_token: Optional[str] = None) -> dict[str, str]:
    env = os.environ.copy()
    api_base = os.getenv("API_BASE_URL")
    if api_base:
        env["API_BASE_URL"] = api_base
    if auth_token:
        env["API_AUTH_TOKEN"] = auth_token
    return env


@asynccontextmanager
async def mcp_session(auth_token: Optional[str] = None):
    server_params = StdioServerParameters(
        command=MCP_SERVER_COMMAND,
        args=[MCP_SERVER_SCRIPT],
        env=_mcp_server_env(auth_token),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _execute_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
    emit: Optional[EmitFn] = None,
) -> str:
    if emit:
        method, path = _tool_http(name, arguments)
        await emit(
            "tool_start",
            {"name": name, "method": method, "path": path, "arguments": arguments},
        )
    result = await session.call_tool(name, arguments)
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(str(block))
    text = "\n".join(parts) if parts else ""
    if emit:
        await emit("tool_end", {"name": name, "preview": text[:300]})
    return text


async def _run_openai_compatible_agent(
    session: ClientSession,
    tools: list[Any],
    message: str,
    history: list[ChatMessage],
    *,
    client: OpenAI,
    model: str,
    emit: Optional[EmitFn] = None,
) -> tuple[str, list[ToolExecution]]:
    openai_tools = [_mcp_tool_to_openai(t) for t in tools]
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": message})

    tool_executions: list[ToolExecution] = []

    for _ in range(8):
        if emit:
            await emit("llm_thinking", {"detail": "Model selecting MCP tools…"})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools if openai_tools else None,
        )
        choice = response.choices[0]
        assistant_message = choice.message

        if assistant_message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
            )
            for tc in assistant_message.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = await _execute_tool(session, tc.function.name, args, emit)
                tool_executions.append(
                    ToolExecution(name=tc.function.name, arguments=args, result=result)
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        reply = assistant_message.content or "Done."
        return reply, tool_executions

    return "I completed the requested actions.", tool_executions


async def _run_openai_agent(
    session: ClientSession,
    tools: list[Any],
    message: str,
    history: list[ChatMessage],
    emit: Optional[EmitFn] = None,
) -> tuple[str, list[ToolExecution]]:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=OPENAI_API_KEY)
    return await _run_openai_compatible_agent(
        session, tools, message, history, client=client, model=OPENAI_MODEL, emit=emit
    )


async def _run_ollama_agent(
    session: ClientSession,
    tools: list[Any],
    message: str,
    history: list[ChatMessage],
    emit: Optional[EmitFn] = None,
) -> tuple[str, list[ToolExecution]]:
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    return await _run_openai_compatible_agent(
        session, tools, message, history, client=client, model=OLLAMA_MODEL, emit=emit
    )


async def _run_anthropic_agent(
    session: ClientSession,
    tools: list[Any],
    message: str,
    history: list[ChatMessage],
    emit: Optional[EmitFn] = None,
) -> tuple[str, list[ToolExecution]]:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not configured")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    anthropic_tools = [_mcp_tool_to_anthropic(t) for t in tools]
    messages: list[dict[str, Any]] = []
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": message})

    tool_executions: list[ToolExecution] = []

    for _ in range(8):
        if emit:
            await emit("llm_thinking", {"detail": "Model selecting MCP tools…"})
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=anthropic_tools,
            messages=messages,
        )

        tool_uses = [block for block in response.content if block.type == "tool_use"]
        text_blocks = [block.text for block in response.content if block.type == "text"]

        if tool_uses:
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tool_use in tool_uses:
                result = await _execute_tool(session, tool_use.name, tool_use.input, emit)
                tool_executions.append(
                    ToolExecution(name=tool_use.name, arguments=tool_use.input, result=result)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue

        reply = " ".join(text_blocks).strip() or "Done."
        return reply, tool_executions

    return "I completed the requested actions.", tool_executions


def _friendly_error(exc: BaseException) -> str:
    """Unwrap TaskGroup/ExceptionGroup so the UI shows the real cause."""
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            msg = _friendly_error(sub)
            if msg:
                return msg
    name = type(exc).__name__
    text = str(exc).strip()
    if "authentication_error" in text or name == "AuthenticationError":
        key = (
            "ANTHROPIC_API_KEY"
            if AI_PROVIDER == "anthropic"
            else "OPENAI_API_KEY"
        )
        return f"Invalid or missing API key for {AI_PROVIDER}. Set {key} in agent/.env"
    if "Connection refused" in text or "ConnectError" in name:
        return (
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            "Run: ollama serve  (and ensure the model is pulled: ollama pull qwen2:7b)"
        )
    if text:
        return text
    return name


async def run_agent(
    message: str,
    history: list[ChatMessage],
    emit: Optional[EmitFn] = None,
    auth_token: Optional[str] = None,
) -> ChatResponse:
    if emit:
        await emit("mcp_spawn", {"detail": "Spawning MCP server subprocess (stdio)"})

    async with mcp_session(auth_token) as session:
        listed = await session.list_tools()
        tools = listed.tools

        if emit:
            await emit("mcp_tools", {"tools": [t.name for t in tools]})

        if AI_PROVIDER == "anthropic":
            reply, tool_executions = await _run_anthropic_agent(
                session, tools, message, history, emit
            )
        elif AI_PROVIDER == "openai":
            reply, tool_executions = await _run_openai_agent(
                session, tools, message, history, emit
            )
        elif AI_PROVIDER == "ollama":
            reply, tool_executions = await _run_ollama_agent(
                session, tools, message, history, emit
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Unsupported AI_PROVIDER: {AI_PROVIDER}. "
                    "Use 'ollama', 'openai', or 'anthropic'."
                ),
            )

        if emit:
            await emit("message", {"reply": reply})

        return ChatResponse(reply=reply, tool_executions=tool_executions)


app = FastAPI(title="Project Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    info: dict[str, str] = {"status": "ok", "provider": AI_PROVIDER}
    if AI_PROVIDER == "ollama":
        info["model"] = OLLAMA_MODEL
    return info


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    try:
        return await run_agent(
            request.message, request.history, auth_token=_bearer_token(authorization)
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_friendly_error(exc)) from exc


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, authorization: Optional[str] = Header(None)):
    import asyncio

    auth_token = _bearer_token(authorization)
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def emit(event: str, data: dict[str, Any]) -> None:
        await queue.put((event, data))

    async def run() -> None:
        try:
            result = await run_agent(request.message, request.history, emit, auth_token)
            await queue.put(("done", {"tool_executions": [t.model_dump() for t in result.tool_executions]}))
        except HTTPException as exc:
            await queue.put(("error", {"message": str(exc.detail)}))
        except Exception as exc:
            await queue.put(("error", {"message": _friendly_error(exc)}))
        finally:
            await queue.put(None)

    async def event_stream():
        task = asyncio.create_task(run())
        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "8001"))
    uvicorn.run("agent:app", host=host, port=port, reload=True)
