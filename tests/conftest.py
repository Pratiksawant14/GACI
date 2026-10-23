"""
Pytest global fixtures.
Provides isolated configuration, temporary directories, and in-memory test database sessions.
"""

import pytest
import os
from app.core.config import Settings


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
