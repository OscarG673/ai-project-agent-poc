"""MCP server that proxies project/requirement operations to the FastAPI REST API."""

import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")

server = Server("requirements-agent")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_AUTH_TOKEN}"} if API_AUTH_TOKEN else {}


def _api_error(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    return f"API error {response.status_code}: {detail}"


async def _request(method: str, path: str, **kwargs: Any) -> str:
    async with httpx.AsyncClient(
        base_url=API_BASE_URL, timeout=30.0, headers=_auth_headers()
    ) as client:
        response = await client.request(method, path, **kwargs)
        if response.status_code == 204:
            return json.dumps({"success": True, "message": "Deleted successfully"})
        if response.is_error:
            return json.dumps({"success": False, "error": _api_error(response)})
        return json.dumps(response.json(), default=str)


ESTADOS = "pendiente, en_progreso, completado, descartado"


def _unwrap_items(result: str) -> str:
    """List endpoints return a paginated envelope; give the LLM just the items."""
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return result
    if isinstance(data, dict) and "items" in data:
        return json.dumps(data["items"], default=str)
    return result


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Proyectos ──
        Tool(
            name="crear_proyecto",
            description="Crea un proyecto nuevo con nombre y descripción opcional.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del proyecto"},
                    "descripcion": {"type": "string", "description": "Descripción"},
                    "init_date": {"type": "string", "description": "Fecha inicio (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "Fecha fin (YYYY-MM-DD)"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="listar_proyectos",
            description="Lista todos los proyectos del usuario.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="obtener_proyecto",
            description="Obtiene un proyecto por su ID numérico.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        ),
        Tool(
            name="actualizar_proyecto",
            description="Actualiza un proyecto por ID. Solo cambia los campos provistos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "init_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="eliminar_proyecto",
            description="Elimina un proyecto por su ID numérico.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        ),
        # ── Requerimientos ──
        Tool(
            name="crear_requerimiento",
            description=(
                "Crea un requerimiento dentro de un proyecto. "
                "prioridad es un entero de 1 (más alta) a 5 (más baja)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "ID del proyecto"},
                    "name": {"type": "string", "description": "Nombre del requerimiento"},
                    "descripcion": {"type": "string"},
                    "prioridad": {"type": "integer", "description": "1 a 5", "default": 3},
                    "estado": {"type": "string", "description": f"Uno de: {ESTADOS}"},
                },
                "required": ["project_id", "name", "prioridad"],
            },
        ),
        Tool(
            name="listar_requerimientos",
            description="Lista los requerimientos de un proyecto.",
            inputSchema={
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
            },
        ),
        Tool(
            name="actualizar_requerimiento",
            description=(
                "Actualiza un requerimiento por ID. Solo cambia los campos provistos. "
                f"estado puede ser: {ESTADOS}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "prioridad": {"type": "integer", "description": "1 a 5"},
                    "estado": {"type": "string", "description": f"Uno de: {ESTADOS}"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="eliminar_requerimiento",
            description="Elimina un requerimiento por su ID numérico.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    # Drop empty/None optional fields the model may send (e.g. init_date="")
    # so they don't trip validation on create/update.
    arguments = {k: v for k, v in arguments.items() if v not in (None, "")}

    if name == "crear_proyecto":
        result = await _request("POST", "/proyectos", json=arguments)

    elif name == "listar_proyectos":
        result = _unwrap_items(
            await _request("GET", "/proyectos", params={"page_size": 100})
        )

    elif name == "obtener_proyecto":
        result = await _request("GET", f"/proyectos/{arguments['id']}")

    elif name == "actualizar_proyecto":
        pid = arguments.pop("id")
        result = await _request("PUT", f"/proyectos/{pid}", json=arguments)

    elif name == "eliminar_proyecto":
        result = await _request("DELETE", f"/proyectos/{arguments['id']}")

    elif name == "crear_requerimiento":
        project_id = arguments.pop("project_id")
        result = await _request(
            "POST", f"/proyectos/{project_id}/requerimientos", json=arguments
        )

    elif name == "listar_requerimientos":
        result = _unwrap_items(
            await _request(
                "GET",
                f"/proyectos/{arguments['project_id']}/requerimientos",
                params={"page_size": 100},
            )
        )

    elif name == "actualizar_requerimiento":
        rid = arguments.pop("id")
        result = await _request("PUT", f"/requerimientos/{rid}", json=arguments)

    elif name == "eliminar_requerimiento":
        result = await _request("DELETE", f"/requerimientos/{arguments['id']}")

    else:
        result = json.dumps({"success": False, "error": f"Unknown tool: {name}"})

    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
