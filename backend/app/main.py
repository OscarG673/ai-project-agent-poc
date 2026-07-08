import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User
from app.routers import auth, projects

load_dotenv()

Base.metadata.create_all(bind=engine)


def seed_admin() -> None:
    """Create the seeded admin user from env vars if it doesn't exist yet."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing is None:
            db.add(User(username=username, password_hash=hash_password(password)))
            db.commit()
    finally:
        db.close()


seed_admin()

app = FastAPI(title="Project Manager API", version="1.0.0")

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)


@app.get("/health")
def health():
    return {"status": "ok"}
