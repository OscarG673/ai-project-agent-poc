"""MCP server that proxies project operations to the FastAPI REST API."""

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

server = Server("project-manager")


def _api_error(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    return f"API error {response.status_code}: {detail}"


async def _request(method: str, path: str, **kwargs: Any) -> str:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        response = await client.request(method, path, **kwargs)
        if response.status_code == 204:
            return json.dumps({"success": True, "message": "Deleted successfully"})
        if response.is_error:
            return json.dumps({"success": False, "error": _api_error(response)})
        return json.dumps(response.json(), default=str)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_project",
            description="Create a new project with name, optional description, and status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "description": {
                        "type": "string",
                        "description": "Project description",
                        "default": "",
                    },
                    "status": {
                        "type": "string",
                        "description": "Project status (e.g. active, completed, archived)",
                        "default": "active",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="list_projects",
            description="List all projects.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_project",
            description="Get a single project by its numeric ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Project ID"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="update_project",
            description="Update an existing project by ID. Only provided fields are changed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Project ID"},
                    "name": {"type": "string", "description": "New project name"},
                    "description": {"type": "string", "description": "New description"},
                    "status": {"type": "string", "description": "New status"},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="delete_project",
            description="Delete a project by its numeric ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Project ID"},
                },
                "required": ["id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "create_project":
        payload = {
            "name": arguments["name"],
            "description": arguments.get("description", ""),
            "status": arguments.get("status", "active"),
        }
        result = await _request("POST", "/projects", json=payload)

    elif name == "list_projects":
        result = await _request("GET", "/projects")

    elif name == "get_project":
        project_id = arguments["id"]
        result = await _request("GET", f"/projects/{project_id}")

    elif name == "update_project":
        project_id = arguments.pop("id")
        result = await _request("PUT", f"/projects/{project_id}", json=arguments)

    elif name == "delete_project":
        project_id = arguments["id"]
        result = await _request("DELETE", f"/projects/{project_id}")

    else:
        result = json.dumps({"success": False, "error": f"Unknown tool: {name}"})

    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
