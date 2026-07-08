from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, verify_password
from app.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, TokenResponse, UsuarioResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.username == payload.username).first()
    if not user or not verify_password(payload.password, user.pass_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.status:
        raise HTTPException(status_code=403, detail="User is inactive")

    token = create_access_token(subject=user.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UsuarioResponse)
def me(current_user: Usuario = Depends(get_current_user)):
    return current_user
