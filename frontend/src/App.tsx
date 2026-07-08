import { useEffect, useState } from "react";
import AgentBubble from "./components/AgentBubble";
import Login from "./components/Login";
import ProyectosDashboard from "./components/ProyectosDashboard";
import { clearToken, getToken, setUnauthorizedHandler } from "./api";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [authed, setAuthed] = useState(() => Boolean(getToken()));

  const bumpRefresh = () => setRefreshKey((key) => key + 1);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
  }, []);

  const handleLogout = () => {
    clearToken();
    setAuthed(false);
  };

  if (!authed) {
    return <Login onLoggedIn={() => setAuthed(true)} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Requirements Agent</h1>
          <p className="muted">Proyectos y requerimientos · Agente en la esquina</p>
        </div>
        <button className="secondary" onClick={handleLogout}>
          Log out
        </button>
      </header>

      <main className="app-main">
        <ProyectosDashboard refreshKey={refreshKey} onProjectsChanged={bumpRefresh} />
      </main>

      <AgentBubble onProjectsChanged={bumpRefresh} />
    </div>
  );
}
