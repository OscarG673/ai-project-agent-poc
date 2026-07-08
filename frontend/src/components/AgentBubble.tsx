import { useEffect, useRef, useState } from "react";
import {
  ChatMessage,
  streamAgentMessage,
  ToolExecution,
} from "../api";
import McpFlowPanel, { McpFlowStep } from "./McpFlowPanel";

interface AgentBubbleProps {
  onProjectsChanged: () => void;
}

const SUGGESTIONS = [
  "Crea un proyecto llamado Sistema RRHH",
  "Muéstrame todos mis proyectos",
  "Agrega un requerimiento de prioridad 1 al proyecto Sistema RRHH",
];

const TOOL_LABELS: Record<string, string> = {
  crear_proyecto: "Crear proyecto",
  listar_proyectos: "Listar proyectos",
  obtener_proyecto: "Ver proyecto",
  actualizar_proyecto: "Actualizar proyecto",
  eliminar_proyecto: "Eliminar proyecto",
  crear_requerimiento: "Crear requerimiento",
  listar_requerimientos: "Listar requerimientos",
  actualizar_requerimiento: "Actualizar requerimiento",
  eliminar_requerimiento: "Eliminar requerimiento",
};

function summarizeToolArgs(name: string, args: Record<string, unknown>): string {
  if (name.startsWith("crear_") && args.name) return `"${args.name}"`;
  if (name === "actualizar_requerimiento" && args.estado)
    return `id ${args.id} → ${args.estado}`;
  if (name === "actualizar_proyecto" && args.name)
    return `id ${args.id} → "${args.name}"`;
  if (args.id !== undefined) return `id ${args.id}`;
  if (args.project_id !== undefined) return `proyecto ${args.project_id}`;
  return "";
}

function ToolTimeline({ tools }: { tools: ToolExecution[] }) {
  const [expanded, setExpanded] = useState(false);
  if (tools.length === 0) return null;

  return (
    <div className="tool-timeline">
      <button
        type="button"
        className="tool-timeline-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="tool-timeline-icon">⚡</span>
        {tools.length} MCP action{tools.length > 1 ? "s" : ""}
        <span className="tool-timeline-chevron">{expanded ? "▾" : "▸"}</span>
      </button>
      <ul className={`tool-steps ${expanded ? "expanded" : ""}`}>
        {tools.map((tool, i) => (
          <li key={i} className="tool-step">
            <span className="tool-step-name">{TOOL_LABELS[tool.name] ?? tool.name}</span>
            {summarizeToolArgs(tool.name, tool.arguments) && (
              <span className="tool-step-args">
                {summarizeToolArgs(tool.name, tool.arguments)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AgentBubble({ onProjectsChanged }: AgentBubbleProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flowStep, setFlowStep] = useState<McpFlowStep>({ phase: "idle" });
  const [flowActive, setFlowActive] = useState(false);
  const [streamingReply, setStreamingReply] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, flowStep, streamingReply, open]);

  const handleSend = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || loading) return;

    if (!open) setOpen(true);

    const userMessage: ChatMessage = { role: "user", content: message };
    const history = [...messages, userMessage];
    setMessages(history);
    setInput("");
    setLoading(true);
    setFlowActive(true);
    setFlowStep({ phase: "mcp_spawn", detail: "Starting…" });
    setStreamingReply("");
    setError(null);

    if (textareaRef.current) textareaRef.current.style.height = "auto";

    let toolExecutions: ToolExecution[] = [];
    let reply = "";

    try {
      await streamAgentMessage(message, messages, (ev) => {
        switch (ev.event) {
          case "mcp_spawn":
            setFlowStep({ phase: "mcp_spawn", detail: ev.data.detail });
            break;
          case "mcp_tools":
            setFlowStep({ phase: "mcp_tools", tools: ev.data.tools });
            break;
          case "llm_thinking":
            setFlowStep({ phase: "llm_thinking", detail: ev.data.detail });
            break;
          case "tool_start":
            setFlowStep({
              phase: "tool_running",
              name: ev.data.name,
              method: ev.data.method,
              path: ev.data.path,
              arguments: ev.data.arguments,
            });
            break;
          case "tool_end":
            setFlowStep({
              phase: "tool_done",
              name: ev.data.name,
              preview: ev.data.preview,
            });
            break;
          case "message":
            reply = ev.data.reply;
            setStreamingReply(ev.data.reply);
            setFlowStep({ phase: "reply", content: ev.data.reply });
            break;
          case "done":
            toolExecutions = ev.data.tool_executions;
            break;
          case "error":
            setError(ev.data.message);
            setFlowStep({ phase: "error", message: ev.data.message });
            break;
        }
      });

      if (reply) {
        setMessages([
          ...history,
          { role: "assistant", content: reply, toolExecutions },
        ]);
        if (toolExecutions.length > 0) onProjectsChanged();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Agent request failed";
      setError(msg);
      setFlowStep({ phase: "error", message: msg });
    } finally {
      setLoading(false);
      setStreamingReply("");
      setTimeout(() => setFlowActive(false), 2500);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 88)}px`;
  };

  return (
    <div className="agent-bubble-root">
      {open && (
        <div className="bubble-panel" role="dialog" aria-label="Agente de requerimientos">
          <header className="bubble-header">
            <div className="chat-header-info">
              <span className="chat-avatar">AI</span>
              <div>
                <h2>Agente</h2>
                <p className="muted">MCP · Ollama</p>
              </div>
            </div>
            <div className="bubble-header-actions">
              <span className="chat-status-dot" title="Online" />
              <button
                type="button"
                className="bubble-icon-btn"
                onClick={() => setOpen(false)}
                aria-label="Minimize"
              >
                ─
              </button>
            </div>
          </header>

          {(flowActive || loading) && (
            <div className="bubble-mcp">
              <McpFlowPanel step={flowStep} active={flowActive || loading} />
            </div>
          )}

          <div className="bubble-messages">
            {messages.length === 0 && !loading && (
              <div className="chat-welcome bubble-welcome">
                <p className="chat-welcome-title">Hi! I manage your projects.</p>
                <div className="suggestion-chips">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="suggestion-chip"
                      onClick={() => void handleSend(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, index) => (
              <div key={index} className={`message-row message-${msg.role}`}>
                {msg.role === "assistant" && (
                  <span className="message-avatar assistant-avatar">AI</span>
                )}
                <div className="message-content">
                  <p>{msg.content}</p>
                  {msg.toolExecutions && msg.toolExecutions.length > 0 && (
                    <ToolTimeline tools={msg.toolExecutions} />
                  )}
                </div>
                {msg.role === "user" && (
                  <span className="message-avatar user-avatar">You</span>
                )}
              </div>
            ))}

            {loading && streamingReply && (
              <div className="message-row message-assistant">
                <span className="message-avatar assistant-avatar">AI</span>
                <div className="message-content">
                  <p>{streamingReply}</p>
                </div>
              </div>
            )}

            {loading && !streamingReply && (
              <div className="message-row message-assistant">
                <span className="message-avatar assistant-avatar">AI</span>
                <div className="message-content typing">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            )}

            {error && (
              <div className="chat-error">
                <span>⚠</span> {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <footer className="chat-composer bubble-composer">
            <textarea
              ref={textareaRef}
              rows={1}
              placeholder="Ask anything..."
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              type="button"
              className="send-btn"
              onClick={() => void handleSend()}
              disabled={loading || !input.trim()}
              aria-label="Send"
            >
              {loading ? "…" : "↑"}
            </button>
          </footer>
        </div>
      )}

      <button
        type="button"
        className={`bubble-fab ${loading ? "bubble-fab-busy" : ""} ${open ? "bubble-fab-hidden" : ""}`}
        onClick={() => setOpen(true)}
        aria-label="Abrir agente"
      >
        {loading ? (
          <span className="bubble-fab-pulse" />
        ) : (
          <>
            <span className="bubble-fab-icon">✦</span>
            <span className="bubble-fab-label">Agent</span>
          </>
        )}
      </button>
    </div>
  );
}
