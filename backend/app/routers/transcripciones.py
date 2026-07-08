from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Proyecto, Transcripcion, Usuario
from app.pagination import Page, PageParams, build_page
from app.schemas import TranscripcionCreate, TranscripcionResponse

router = APIRouter(prefix="/transcripciones", tags=["transcripciones"])


def _check_proyecto(project_id: int | None, db: Session, user: Usuario) -> None:
    if project_id is None:
        return
    proyecto = db.get(Proyecto, project_id)
    if not proyecto or proyecto.usuario_id != user.id:
        raise HTTPException(status_code=404, detail=f"Proyecto {project_id} not found")


@router.post("", response_model=TranscripcionResponse, status_code=status.HTTP_201_CREATED)
def create_transcripcion(
    payload: TranscripcionCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    _check_proyecto(payload.project_id, db, user)
    transcripcion = Transcripcion(**payload.model_dump(), usuario_id=user.id)
    db.add(transcripcion)
    db.commit()
    db.refresh(transcripcion)
    return transcripcion


@router.get("", response_model=Page[TranscripcionResponse])
def list_transcripciones(
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    query = db.query(Transcripcion).filter(Transcripcion.usuario_id == user.id)
    total = query.count()
    items = (
        query.order_by(Transcripcion.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
        .all()
    )
    return build_page(items, total, params)


@router.get("/{transcripcion_id}", response_model=TranscripcionResponse)
def get_transcripcion(
    transcripcion_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    transcripcion = db.get(Transcripcion, transcripcion_id)
    if not transcripcion or transcripcion.usuario_id != user.id:
        raise HTTPException(
            status_code=404, detail=f"Transcripcion {transcripcion_id} not found"
        )
    return transcripcion
