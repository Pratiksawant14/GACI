"""
Unit test suite for app/core/config.py.
Verifies safe configuration loading, defaults, and property derivations.
"""

from app.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.APP_NAME == "Graph-Based Cash-Flow Intelligence System"
    assert settings.ENVIRONMENT in ["development", "testing", "production"]
    assert settings.POSTGRES_PORT == 5432
    assert "postgresql+psycopg2://" in settings.SQLALCHEMY_DATABASE_URI


def test_override_database_url():
    custom_url = "sqlite:///./custom_test.db"
    settings = Settings(DATABASE_URL=custom_url)
    assert settings.DATABASE_URL == custom_url
    assert settings.SQLALCHEMY_DATABASE_URI == custom_url


def test_fixture_settings(test_settings):
    assert test_settings.ENVIRONMENT == "testing"
    assert test_settings.DATABASE_URL == "sqlite:///:memory:"
