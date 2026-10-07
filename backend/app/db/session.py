from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings

# Engine configuration with connection pooling
import logging
from sqlalchemy import text
from app.db.base import Base

logger = logging.getLogger(__name__)

connect_args = {}
db_url = settings.DATABASE_URL
engine = None

if settings.ENVIRONMENT == "test" or db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args=connect_args,
        poolclass=StaticPool,
        future=True,
    )
else:
    import socket
    from urllib.parse import urlparse
    
    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    
    pg_available = False
    try:
        with socket.create_connection((host, port), timeout=0.3):
            pg_available = True
    except OSError:
        pg_available = False

    if pg_available:
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        try:
            candidate_engine = create_engine(
                db_url,
                echo=False,
                future=True,
                connect_args={"connect_timeout": 2},
                pool_pre_ping=True,
            )
            # Test connection
            with candidate_engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            engine = candidate_engine
            logger.info("Connected to PostgreSQL database successfully.")
        except Exception as e:
            logger.warning(
                f"Could not connect to PostgreSQL at {db_url} ({e}). "
                "Falling back to local SQLite database at sqlite:///./knowledgehub_dev.db"
            )
            engine = create_engine(
                "sqlite:///./knowledgehub_dev.db",
                connect_args={"check_same_thread": False},
                future=True,
            )
    else:
        logger.info(
            f"PostgreSQL service unreachable at {host}:{port}. "
            "Falling back to local SQLite database at sqlite:///./knowledgehub_dev.db"
        )
        engine = create_engine(
            "sqlite:///./knowledgehub_dev.db",
            connect_args={"check_same_thread": False},
            future=True,
        )

# If SQLite is active, ensure all models are registered and tables are created
if engine.dialect.name == "sqlite":
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
