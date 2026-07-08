from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Proyecto, Usuario, utcnow
from app.pagination import Page, PageParams, build_page
from app.schemas import ProyectoCreate, ProyectoResponse, ProyectoUpdate

router = APIRouter(prefix="/proyectos", tags=["proyectos"])


def _owned(project_id: int, db: Session, user: Usuario) -> Proyecto:
    proyecto = db.get(Proyecto, project_id)
    if not proyecto or proyecto.usuario_id != user.id:
        raise HTTPException(status_code=404, detail=f"Proyecto {project_id} not found")
    return proyecto


@router.post("", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
def create_proyecto(
    payload: ProyectoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    proyecto = Proyecto(**payload.model_dump(), usuario_id=user.id)
    db.add(proyecto)
    db.commit()
    db.refresh(proyecto)
    return proyecto


@router.get("", response_model=Page[ProyectoResponse])
def list_proyectos(
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    query = db.query(Proyecto).filter(Proyecto.usuario_id == user.id)
    total = query.count()
    items = (
        query.order_by(Proyecto.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
        .all()
    )
    return build_page(items, total, params)


@router.get("/{project_id}", response_model=ProyectoResponse)
def get_proyecto(
    project_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return _owned(project_id, db, user)


@router.put("/{project_id}", response_model=ProyectoResponse)
def update_proyecto(
    project_id: int,
    payload: ProyectoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    proyecto = _owned(project_id, db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(proyecto, field, value)
    proyecto.updated_at = utcnow()
    db.commit()
    db.refresh(proyecto)
    return proyecto


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proyecto(
    project_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    proyecto = _owned(project_id, db, user)
    db.delete(proyecto)
    db.commit()
    return None
