import { useState } from "react";
import { useAudioRecorder } from "./useAudioRecorder";

function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ animation: "mt-spin 0.8s linear infinite" }}>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

export default function MicTest() {
  const recorder = useAudioRecorder();
  const [texto, setTexto] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const handleClick = async () => {
    setErr(null);
    if (recorder.status === "recording") {
      try {
        const t = await recorder.stopAndTranscribe();
        setTexto((prev) => (prev ? `${prev} ${t}` : t));
      } catch {
        setErr(recorder.error ?? "Error al transcribir");
      }
    } else if (recorder.status === "idle") {
      await recorder.start().catch(() => setErr(recorder.error ?? "No se pudo grabar"));
    }
  };

  const { status } = recorder;
  const icon =
    status === "recording" ? <StopIcon /> : status === "transcribing" ? <SpinnerIcon /> : <MicIcon />;
  const label =
    status === "recording" ? "Detener y transcribir" : status === "transcribing" ? "Transcribiendo" : "Grabar";

  return (
    <div style={{ maxWidth: 600, margin: "3rem auto", fontFamily: "system-ui", color: "#e7ecf3" }}>
      <style>{`@keyframes mt-spin { to { transform: rotate(360deg); } }`}</style>

      <h2>Prueba de micrófono → texto</h2>
      <p style={{ color: "#9aa7b8" }}>Graba, para, y mira la transcripción. Usa el STT (Whisper) en el 8002.</p>

      <button
        onClick={() => void handleClick()}
        disabled={status === "transcribing"}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.7rem 1.2rem",
          fontSize: "1rem",
          borderRadius: 10,
          border: "none",
          background: status === "recording" ? "#b91c1c" : "#3b82f6",
          color: "white",
          cursor: status === "transcribing" ? "default" : "pointer",
        }}
      >
        {icon}
        {label}
      </button>

      {err && <p style={{ color: "#fca5a5", marginTop: "1rem" }}>⚠ {err}</p>}

      <div
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          minHeight: 80,
          borderRadius: 10,
          background: "#141b26",
          border: "1px solid #243044",
          whiteSpace: "pre-wrap",
        }}
      >
        {texto || <span style={{ color: "#6b7a8d" }}>La transcripción aparecerá acá…</span>}
      </div>

      {texto && (
        <button
          onClick={() => setTexto("")}
          style={{ marginTop: "0.75rem", padding: "0.4rem 0.8rem", borderRadius: 8, border: "1px solid #2f3d52", background: "transparent", color: "#c5d0de", cursor: "pointer" }}
        >
          Limpiar
        </button>
      )}
    </div>
  );
}
