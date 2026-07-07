import { useEffect, useState } from "react";

export type McpFlowStep =
  | { phase: "idle" }
  | { phase: "mcp_spawn"; detail: string }
  | { phase: "mcp_tools"; tools: string[] }
  | { phase: "llm_thinking"; detail: string }
  | { phase: "tool_running"; name: string; method: string; path: string; arguments: Record<string, unknown> }
  | { phase: "tool_done"; name: string; preview: string }
  | { phase: "reply"; content: string }
  | { phase: "error"; message: string };

interface McpFlowPanelProps {
  step: McpFlowStep;
  active: boolean;
}

const NODES = ["Agent", "MCP", "API", "SQLite"] as const;

function activeNode(step: McpFlowStep): number {
  switch (step.phase) {
    case "mcp_spawn":
      return 1;
    case "mcp_tools":
      return 1;
    case "llm_thinking":
      return 0;
    case "tool_running":
      return 2;
    case "tool_done":
      return 3;
    case "reply":
      return 0;
    default:
      return -1;
  }
}

export default function McpFlowPanel({ step, active }: McpFlowPanelProps) {
  const [log, setLog] = useState<string[]>([]);
  const nodeIdx = activeNode(step);

  useEffect(() => {
    if (!active) {
      setLog([]);
      return;
    }
    const entry = (() => {
      switch (step.phase) {
        case "mcp_spawn":
          return "→ Spawning MCP server (stdio subprocess)";
        case "mcp_tools":
          return `→ Discovered ${step.tools.length} tools: ${step.tools.join(", ")}`;
        case "llm_thinking":
          return "→ LLM analyzing your message…";
        case "tool_running":
          return `→ call_tool("${step.name}") → ${step.method} ${step.path}`;
        case "tool_done":
          return `✓ ${step.name} completed`;
        case "reply":
          return "→ Generating response";
        case "error":
          return `✗ ${step.message}`;
        default:
          return null;
      }
    })();
    if (entry) setLog((prev) => [...prev, entry]);
  }, [step, active]);

  if (!active && step.phase === "idle") return null;

  return (
    <div className={`mcp-flow ${active ? "mcp-flow-live" : "mcp-flow-done"}`}>
      <div className="mcp-flow-header">
        <span className="mcp-flow-badge">MCP Protocol</span>
        <span className="muted">Agent → stdio → MCP → HTTP → SQLite</span>
      </div>

      <div className="mcp-pipeline">
        {NODES.map((label, i) => (
          <div key={label} className="mcp-pipeline-segment">
            <div
              className={`mcp-node ${i <= nodeIdx && active ? "mcp-node-active" : ""} ${i === nodeIdx && active ? "mcp-node-pulse" : ""}`}
            >
              <span className="mcp-node-icon">
                {label === "Agent" && "🤖"}
                {label === "MCP" && "⚡"}
                {label === "API" && "🔌"}
                {label === "SQLite" && "💾"}
              </span>
              <span className="mcp-node-label">{label}</span>
            </div>
            {i < NODES.length - 1 && (
              <div className={`mcp-connector ${i < nodeIdx && active ? "mcp-connector-active" : ""}`}>
                <span className="mcp-connector-arrow">›</span>
                {i === 0 && <span className="mcp-connector-tag">stdio</span>}
                {i === 1 && <span className="mcp-connector-tag">HTTP</span>}
                {i === 2 && <span className="mcp-connector-tag">SQL</span>}
              </div>
            )}
          </div>
        ))}
      </div>

      {step.phase === "tool_running" && (
        <div className="mcp-tool-call">
          <code>call_tool</code>
          <span className="mcp-tool-name">{step.name}</span>
          <span className="mcp-http-badge">{step.method} {step.path}</span>
        </div>
      )}

      <ul className="mcp-log">
        {log.map((line, i) => (
          <li key={i} className={line.startsWith("✓") ? "log-ok" : line.startsWith("✗") ? "log-err" : ""}>
            {line}
          </li>
        ))}
      </ul>
    </div>
  );
}
