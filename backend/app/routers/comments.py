from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Comment, Requerimiento, Usuario
from app.pagination import Page, PageParams, build_page
from app.schemas import CommentCreate, CommentResponse

router = APIRouter(tags=["comments"])


def _owned_requerimiento(req_id: int, db: Session, user: Usuario) -> Requerimiento:
    req = db.get(Requerimiento, req_id)
    if not req or req.proyecto.usuario_id != user.id:
        raise HTTPException(status_code=404, detail=f"Requerimiento {req_id} not found")
    return req


@router.post(
    "/requerimientos/{req_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    req_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    _owned_requerimiento(req_id, db, user)
    comment = Comment(
        requerimiento_id=req_id,
        usuario_id=user.id,
        description=payload.description,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get(
    "/requerimientos/{req_id}/comments",
    response_model=Page[CommentResponse],
)
def list_comments(
    req_id: int,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    _owned_requerimiento(req_id, db, user)
    query = db.query(Comment).filter(Comment.requerimiento_id == req_id)
    total = query.count()
    items = (
        query.order_by(Comment.created_at.asc())
        .offset(params.offset)
        .limit(params.page_size)
        .all()
    )
    return build_page(items, total, params)


@router.delete(
    "/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    comment = db.get(Comment, comment_id)
    if not comment or comment.requerimiento.proyecto.usuario_id != user.id:
        raise HTTPException(status_code=404, detail=f"Comment {comment_id} not found")
    db.delete(comment)
    db.commit()
    return None
