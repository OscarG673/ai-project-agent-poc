const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const AGENT_URL = import.meta.env.VITE_AGENT_URL ?? "http://localhost:8001";

const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Callback invoked when any request gets a 401 (e.g. expired token). */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectInput {
  name: string;
  description: string;
  status: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolExecutions?: ToolExecution[];
}

export interface ToolExecution {
  name: string;
  arguments: Record<string, unknown>;
  result: string;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearToken();
    onUnauthorized?.();
  }
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export interface CurrentUser {
  id: number;
  username: string;
  status: boolean;
  created_at: string;
}

export async function login(username: string, password: string): Promise<string> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await handleResponse<{ access_token: string }>(response);
  setToken(data.access_token);
  return data.access_token;
}

export async function fetchMe(): Promise<CurrentUser> {
  const response = await fetch(`${API_URL}/auth/me`, {
    headers: authHeaders(),
  });
  return handleResponse<CurrentUser>(response);
}

export async function fetchProjects(): Promise<Project[]> {
  const response = await fetch(`${API_URL}/projects`, {
    headers: authHeaders(),
  });
  return handleResponse<Project[]>(response);
}

export async function createProject(data: ProjectInput): Promise<Project> {
  const response = await fetch(`${API_URL}/projects`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return handleResponse<Project>(response);
}

export async function updateProject(
  id: number,
  data: Partial<ProjectInput>
): Promise<Project> {
  const response = await fetch(`${API_URL}/projects/${id}`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return handleResponse<Project>(response);
}

export async function deleteProject(id: number): Promise<void> {
  const response = await fetch(`${API_URL}/projects/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse<void>(response);
}

export async function sendAgentMessage(
  message: string,
  history: ChatMessage[]
): Promise<{ reply: string; tool_executions: ToolExecution[] }> {
  const response = await fetch(`${AGENT_URL}/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      history: history.map(({ role, content }) => ({ role, content })),
    }),
  });
  return handleResponse(response);
}

export type StreamEvent =
  | { event: "mcp_spawn"; data: { detail: string } }
  | { event: "mcp_tools"; data: { tools: string[] } }
  | { event: "llm_thinking"; data: { detail: string } }
  | { event: "tool_start"; data: { name: string; method: string; path: string; arguments: Record<string, unknown> } }
  | { event: "tool_end"; data: { name: string; preview: string } }
  | { event: "message"; data: { reply: string } }
  | { event: "done"; data: { tool_executions: ToolExecution[] } }
  | { event: "error"; data: { message: string } };

export async function streamAgentMessage(
  message: string,
  history: ChatMessage[],
  onEvent: (event: StreamEvent) => void
): Promise<void> {
  const response = await fetch(`${AGENT_URL}/chat/stream`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      history: history.map(({ role, content }) => ({ role, content })),
    }),
  });

  if (response.status === 401) {
    clearToken();
    onUnauthorized?.();
  }
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const lines = part.split("\n");
      let eventType = "";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) eventType = line.slice(7);
        if (line.startsWith("data: ")) dataStr = line.slice(6);
      }
      if (eventType && dataStr) {
        onEvent({ event: eventType, data: JSON.parse(dataStr) } as StreamEvent);
      }
    }
  }
}
