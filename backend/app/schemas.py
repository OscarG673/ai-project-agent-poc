from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import EstadoRequerimiento

# ── Auth ──────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    status: bool
    created_at: datetime


# ── Proyectos ─────────────────────────────────────────────────────────


class ProyectoBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    descripcion: Optional[str] = None
    init_date: Optional[date] = None
    end_date: Optional[date] = None


class ProyectoCreate(ProyectoBase):
    pass


class ProyectoUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    descripcion: Optional[str] = None
    init_date: Optional[date] = None
    end_date: Optional[date] = None


class ProyectoResponse(ProyectoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    created_at: datetime
    updated_at: datetime


# ── Requerimientos ────────────────────────────────────────────────────


class RequerimientoBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    prioridad: int = Field(..., ge=1, le=5)
    estado: EstadoRequerimiento = EstadoRequerimiento.pendiente
    transcripcion_id: Optional[int] = None


class RequerimientoCreate(RequerimientoBase):
    pass


class RequerimientoUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = None
    prioridad: Optional[int] = Field(None, ge=1, le=5)
    estado: Optional[EstadoRequerimiento] = None
    transcripcion_id: Optional[int] = None


class RequerimientoResponse(RequerimientoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime


# ── Comments ──────────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    description: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requerimiento_id: int
    usuario_id: Optional[int]
    description: str
    created_at: datetime


# ── Transcripciones ───────────────────────────────────────────────────


class TranscripcionCreate(BaseModel):
    project_id: Optional[int] = None
    audio_path: Optional[str] = None
    texto_stt: Optional[str] = None
    respuesta_llm: Optional[dict[str, Any]] = None
    modelo_stt: Optional[str] = "whisper-small"
    modelo_llm: Optional[str] = "llama3.1"
    tool_calls: Optional[dict[str, Any]] = None


class TranscripcionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    project_id: Optional[int]
    audio_path: Optional[str]
    texto_stt: Optional[str]
    respuesta_llm: Optional[dict[str, Any]]
    modelo_stt: Optional[str]
    modelo_llm: Optional[str]
    tool_calls: Optional[dict[str, Any]]
    created_at: datetime
