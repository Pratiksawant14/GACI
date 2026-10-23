"""
SQLAlchemy Database Session and Engine Management.
Provides scoped session factories, connection pooling, and transactional context managers.
"""

from typing import Generator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.logging import logger


def create_db_engine(database_url: str = settings.SQLALCHEMY_DATABASE_URI):
    """Creates an engine configured with appropriate pool settings."""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False
    )


engine = create_db_engine()
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db: Session = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context(database_url: str = None) -> Generator[Session, None, None]:
    """Context manager for standalone service tasks and worker scripts."""
    if database_url:
        custom_engine = create_db_engine(database_url)
        custom_factory = sessionmaker(autocommit=False, autoflush=False, bind=custom_engine)
        session = custom_factory()
    else:
        session = SessionFactory()

    try:
        yield session
    finally:
        session.close()


@contextmanager
def transactional(session: Session) -> Generator[Session, None, None]:
    """Context manager enforcing ACID commit or rollback."""
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"Transaction rolled back due to error: {exc}")
        raise
