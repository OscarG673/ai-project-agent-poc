import { useEffect, useState } from "react";
import AgentBubble from "./components/AgentBubble";
import Login from "./components/Login";
import ProyectosDashboard from "./components/ProyectosDashboard";
import MicTest from "./MicTest";
import { clearToken, getToken, setUnauthorizedHandler } from "./api";

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [authed, setAuthed] = useState(() => Boolean(getToken()));
  const [showMic, setShowMic] = useState(false);

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
        <div className="header-actions">
          <button className="secondary" onClick={() => setShowMic((v) => !v)}>
            {showMic ? "Ver proyectos" : "🎤 Prueba de voz"}
          </button>
          <button className="secondary" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <main className="app-main">
        {showMic ? (
          <MicTest />
        ) : (
          <ProyectosDashboard refreshKey={refreshKey} onProjectsChanged={bumpRefresh} />
        )}
      </main>

      <AgentBubble onProjectsChanged={bumpRefresh} />
    </div>
  );
}
