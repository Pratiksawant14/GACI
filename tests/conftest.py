"""
Pytest global fixtures.
Provides isolated configuration, temporary directories, and in-memory test database sessions.
"""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.models.base import Base


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provides test-specific settings with SQLite in-memory fallback for local testing."""
    return Settings(
        ENVIRONMENT="testing",
        LOG_LEVEL="DEBUG",
        DATABASE_URL="sqlite:///:memory:",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="test_password",
        OPENAI_API_KEY="test-mock-key"
    )


from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite session with all tables created and thread sharing enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
