import { useEffect, useState } from "react";
import { setUnauthorizedHandler } from "./api";
import MicTest from "./MicTest";

export default function App() {
  const [, setAuthed] = useState(true);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthed(false));
  }, []);

  // Login desactivado temporalmente (sin base de datos).
  // Para reactivarlo: restaurar el import de Login y el chequeo de authed.
  return <MicTest />;
}
