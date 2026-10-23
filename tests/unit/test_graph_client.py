"""
Unit tests for Neo4j client and schema constraint setup (TSK-08).
"""

from unittest.mock import MagicMock, patch
import pytest
from app.graph.client import Neo4jClient
from app.graph.schema import GRAPH_NODE_CONSTRAINTS, init_graph_schema


def test_neo4j_client_initialization():
    client = Neo4jClient(uri="bolt://localhost:7687", user="test_user", password="test_password")
    assert client.uri == "bolt://localhost:7687"
    assert client.user == "test_user"


def test_neo4j_client_verify_connectivity_offline():
    client = Neo4jClient(uri="bolt://invalid-host:7687", user="u", password="p")
    # Should safely return False rather than crashing the application
    assert client.verify_connectivity() is False


def test_init_graph_schema_with_mocked_driver():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_client.verify_connectivity.return_value = True

    success = init_graph_schema(mock_client)
    assert success is True
    # Verify execute_write was called for all constraints and indexes
    assert mock_client.execute_write.call_count >= len(GRAPH_NODE_CONSTRAINTS)


def test_init_graph_schema_skipped_when_offline():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_client.verify_connectivity.return_value = False

    success = init_graph_schema(mock_client)
    assert success is False
    assert mock_client.execute_write.call_count == 0
