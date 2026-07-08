import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EstadoRequerimiento(str, enum.Enum):
    pendiente = "pendiente"
    en_progreso = "en_progreso"
    completado = "completado"
    descartado = "descartado"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    pass_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )

    proyectos: Mapped[list["Proyecto"]] = relationship(back_populates="usuario")


class Proyecto(Base):
    __tablename__ = "proyectos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    init_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="proyectos")
    requerimientos: Mapped[list["Requerimiento"]] = relationship(
        back_populates="proyecto", cascade="all, delete-orphan"
    )


class Transcripcion(Base):
    __tablename__ = "transcripciones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuarios.id", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("proyectos.id", onupdate="CASCADE", ondelete="SET NULL"),
        index=True,
    )
    audio_path: Mapped[str | None] = mapped_column(Text)
    texto_stt: Mapped[str | None] = mapped_column(Text)
    respuesta_llm: Mapped[dict | None] = mapped_column(JSONB)
    modelo_stt: Mapped[str | None] = mapped_column(String(50), default="whisper-small")
    modelo_llm: Mapped[str | None] = mapped_column(String(50), default="llama3.1")
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Requerimiento(Base):
    __tablename__ = "requerimientos"
    __table_args__ = (
        CheckConstraint("prioridad BETWEEN 1 AND 5", name="ck_requerimientos_prioridad"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("proyectos.id", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    prioridad: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estado: Mapped[EstadoRequerimiento] = mapped_column(
        Enum(EstadoRequerimiento, name="estado_requerimiento"),
        nullable=False,
        default=EstadoRequerimiento.pendiente,
    )
    transcripcion_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("transcripciones.id", onupdate="CASCADE", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )

    proyecto: Mapped["Proyecto"] = relationship(back_populates="requerimientos")
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="requerimiento", cascade="all, delete-orphan"
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requerimiento_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("requerimientos.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", onupdate="CASCADE", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    requerimiento: Mapped["Requerimiento"] = relationship(back_populates="comments")
