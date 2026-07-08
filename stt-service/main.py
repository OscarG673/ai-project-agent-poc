"""
Microservicio de STT (Speech-to-Text) con mlx_whisper.

Recibe audio subido (multipart/form-data), lo transcribe con Whisper
optimizado para Apple Silicon (MLX) y devuelve el texto.

Correr:
    uvicorn main:app --host 0.0.0.0 --port 8001

El backend de conversaciones consume el campo `texto` de la respuesta.
"""

import os
import uuid
import time
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv

import mlx_whisper

load_dotenv()

MODELOS = {
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}
MODELO_DEFAULT = os.getenv("STT_MODELO_DEFAULT", "small")
IDIOMA_DEFAULT = os.getenv("STT_IDIOMA_DEFAULT", "es")

CORS_ORIGINS = os.getenv(
    "STT_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

UPLOAD_DIR = Path(os.getenv("STT_UPLOAD_DIR", str(Path.home() / "stt-uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="STT Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "modelo_default": MODELO_DEFAULT}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    modelo: str = Form(MODELO_DEFAULT),
    idioma: str = Form(IDIOMA_DEFAULT),
):
    if modelo not in MODELOS:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo invalido. Opciones: {list(MODELOS.keys())}",
        )

    ext = Path(audio.filename or "audio").suffix or ".webm"
    audio_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    contenido = await audio.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="Audio vacio")
    audio_path.write_bytes(contenido)

    t0 = time.perf_counter()
    try:
        resultado = await run_in_threadpool(
            mlx_whisper.transcribe,
            str(audio_path),
            path_or_hf_repo=MODELOS[modelo],
            language=idioma,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error transcribiendo: {e}")
    dur = time.perf_counter() - t0

    return {
        "texto": resultado["text"].strip(),
        "idioma": idioma,
        "modelo": modelo,
        "audio_path": str(audio_path),
        "tiempo_transcripcion_s": round(dur, 2),
    }
