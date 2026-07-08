from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Proyecto, Requerimiento, Usuario, utcnow
from app.pagination import Page, PageParams, build_page
from app.schemas import (
    RequerimientoCreate,
    RequerimientoResponse,
    RequerimientoUpdate,
)

router = APIRouter(tags=["requerimientos"])


def _owned_proyecto(project_id: int, db: Session, user: Usuario) -> Proyecto:
    proyecto = db.get(Proyecto, project_id)
    if not proyecto or proyecto.usuario_id != user.id:
        raise HTTPException(status_code=404, detail=f"Proyecto {project_id} not found")
    return proyecto


def _owned_requerimiento(req_id: int, db: Session, user: Usuario) -> Requerimiento:
    req = db.get(Requerimiento, req_id)
    if not req or req.proyecto.usuario_id != user.id:
        raise HTTPException(status_code=404, detail=f"Requerimiento {req_id} not found")
    return req


@router.post(
    "/proyectos/{project_id}/requerimientos",
    response_model=RequerimientoResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_requerimiento(
    project_id: int,
    payload: RequerimientoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    _owned_proyecto(project_id, db, user)
    req = Requerimiento(**payload.model_dump(), project_id=project_id)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get(
    "/proyectos/{project_id}/requerimientos",
    response_model=Page[RequerimientoResponse],
)
def list_requerimientos(
    project_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    _owned_proyecto(project_id, db, user)
    query = db.query(Requerimiento).filter(Requerimiento.project_id == project_id)
    total = query.count()
    items = (
        query.order_by(Requerimiento.prioridad.asc(), Requerimiento.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
        .all()
    )
    return build_page(items, total, params)


@router.get("/requerimientos/{req_id}", response_model=RequerimientoResponse)
def get_requerimiento(
    req_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return _owned_requerimiento(req_id, db, user)


@router.put("/requerimientos/{req_id}", response_model=RequerimientoResponse)
def update_requerimiento(
    req_id: int,
    payload: RequerimientoUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    req = _owned_requerimiento(req_id, db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(req, field, value)
    req.updated_at = utcnow()
    db.commit()
    db.refresh(req)
    return req


@router.delete("/requerimientos/{req_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requerimiento(
    req_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    req = _owned_requerimiento(req_id, db, user)
    db.delete(req)
    db.commit()
    return None
