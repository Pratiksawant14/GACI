"""
Neo4j Schema and Constraint Definitions.
Enforces unique node identifiers across all business, party, and transactional labels.
"""

from typing import List
from app.graph.client import Neo4jClient, neo4j_client
from app.core.logging import logger

GRAPH_NODE_CONSTRAINTS: List[str] = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:Business) REQUIRE b.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplier) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Invoice) REQUIRE i.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Payment) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (a:BankAccount) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (sa:SupplierAdvance) REQUIRE sa.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Delivery) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Obligation) REQUIRE o.id IS UNIQUE",
]

GRAPH_INDEXES: List[str] = [
    "CREATE INDEX IF NOT EXISTS FOR (i:Invoice) ON (i.status)",
    "CREATE INDEX IF NOT EXISTS FOR (i:Invoice) ON (i.due_date)",
    "CREATE INDEX IF NOT EXISTS FOR (sa:SupplierAdvance) ON (sa.expected_delivery_date)",
    "CREATE INDEX IF NOT EXISTS FOR (o:Obligation) ON (o.due_date)",
]


def init_graph_schema(client: Neo4jClient = neo4j_client) -> bool:
    """Initializes uniqueness constraints and secondary indexes in Neo4j."""
    if not client.verify_connectivity():
        logger.warning("Neo4j is not connected. Skipping constraint initialization.")
        return False

    logger.info("Initializing Neo4j uniqueness constraints and indexes...")
    for cypher in GRAPH_NODE_CONSTRAINTS:
        try:
            client.execute_write(cypher)
        except Exception as exc:
            logger.error(f"Failed applying constraint: {cypher}. Error: {exc}")
            raise

    for cypher in GRAPH_INDEXES:
        try:
            client.execute_write(cypher)
        except Exception as exc:
            logger.error(f"Failed applying index: {cypher}. Error: {exc}")
            raise

    logger.info("Neo4j graph schema constraints and indexes initialized successfully.")
    return True
