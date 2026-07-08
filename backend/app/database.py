import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# PostgreSQL via psycopg 3, e.g.
#   postgresql+psycopg://user:password@localhost:5432/requirements_agent
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ania:ania@localhost:5432/requirements_agent",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
