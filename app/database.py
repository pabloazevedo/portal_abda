import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://orchestra_user:orchestra_pass@localhost:5432/orchestra_db")

# Production: Use pool para connection reuse
# Development: NullPool para evitar connection stale
pool_class = NullPool if DATABASE_URL.endswith("localhost:5432/orchestra_db") else None

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
    poolclass=pool_class if pool_class else None,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
