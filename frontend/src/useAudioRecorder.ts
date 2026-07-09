import { useCallback, useRef, useState } from "react";

const AGENT_URL = import.meta.env.VITE_AGENT_URL ?? "http://localhost:8001";

type RecorderStatus = "idle" | "recording" | "transcribing";

interface UseAudioRecorder {
  status: RecorderStatus;
  error: string | null;
  start: () => Promise<void>;
  stopAndTranscribe: () => Promise<string>;
  cancel: () => void;
}

export function useAudioRecorder(): UseAudioRecorder {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.start();
      recorderRef.current = recorder;
      setStatus("recording");
    } catch (err) {
      const msg =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone access denied"
          : "Could not start recording";
      setError(msg);
      setStatus("idle");
      cleanupStream();
      throw err;
    }
  }, [cleanupStream]);

  const stopAndTranscribe = useCallback(async (): Promise<string> => {
    const recorder = recorderRef.current;
    if (!recorder) return "";

    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        resolve(new Blob(chunksRef.current, { type: "audio/webm" }));
      };
      recorder.stop();
    });

    cleanupStream();
    recorderRef.current = null;
    setStatus("transcribing");

    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      form.append("modelo", "large-v3");
      form.append("idioma", "es");

      const response = await fetch(`${AGENT_URL}/transcribe`, {
        method: "POST",
        body: form,
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || `Transcription failed (${response.status})`);
      }

      const data = await response.json();
      setStatus("idle");
      return (data.texto ?? "").trim();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Transcription failed";
      setError(msg);
      setStatus("idle");
      throw err;
    }
  }, [cleanupStream]);

  const cancel = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    cleanupStream();
    chunksRef.current = [];
    setStatus("idle");
  }, [cleanupStream]);

  return { status, error, start, stopAndTranscribe, cancel };
}
