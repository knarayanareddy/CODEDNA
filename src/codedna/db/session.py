"""Database session management for CodeDNA."""
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.orm import Session, sessionmaker

from codedna.config import get_config_dir

logger = logging.getLogger(__name__)
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None

def _create_engine() -> Engine:
    db_path = get_config_dir() / "codedna.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, pool_pre_ping=True, pool_size=5, max_overflow=10, echo=False)
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    return engine

def init_database() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = _create_engine()
        from codedna.db.schema import init_db
        init_db(_engine)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
        logger.info(f"Database initialized at: {get_config_dir() / 'codedna.db'}")
    return _engine

def get_engine() -> Engine:
    if _engine is None:
        return init_database()
    return _engine

@contextmanager
def get_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_raw_connection() -> Connection:
    return get_engine().connect()

def close_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed")

def get_session_factory():
    if _session_factory is None:
        init_database()
    return _session_factory
