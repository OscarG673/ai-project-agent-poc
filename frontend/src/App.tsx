import { useState } from "react";
import AgentBubble from "./components/AgentBubble";
import ProjectsDashboard from "./components/ProjectsDashboard";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  const bumpRefresh = () => setRefreshKey((key) => key + 1);

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>AI Project Manager</h1>
          <p className="muted">Manage projects · Agent in the corner</p>
        </div>
      </header>

      <main className="app-main">
        <ProjectsDashboard refreshKey={refreshKey} onProjectsChanged={bumpRefresh} />
      </main>

      <AgentBubble onProjectsChanged={bumpRefresh} />
    </div>
  );
}
