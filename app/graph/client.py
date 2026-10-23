"""
Neo4j Graph Database Client.
Manages driver connection lifecycle, connection pooling, and parameterized Cypher execution.
"""

from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase, Driver, Session as Neo4jSession
from neo4j.exceptions import ServiceUnavailable, AuthError
from app.core.config import settings
from app.core.logging import logger


class Neo4jClient:
    """Thread-safe client managing Neo4j connection lifecycle."""

    def __init__(
        self,
        uri: str = settings.NEO4J_URI,
        user: str = settings.NEO4J_USER,
        password: str = settings.NEO4J_PASSWORD
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Optional[Driver] = None
        self._last_check_time: float = 0.0
        self._last_check_status: Optional[bool] = None
        self._check_ttl: float = 10.0

    def get_driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_timeout=2.0
            )
        return self._driver

    def verify_connectivity(self, force_refresh: bool = False) -> bool:
        """Verifies if the Neo4j instance is alive and reachable with TTL caching."""
        import time
        now = time.time()
        if not force_refresh and self._last_check_status is not None:
            if (now - self._last_check_time) < self._check_ttl:
                return self._last_check_status

        try:
            driver = self.get_driver()
            driver.verify_connectivity()
            self._last_check_status = True
            self._last_check_time = now
            return True
        except (ServiceUnavailable, AuthError) as exc:
            logger.warning(f"Neo4j instance at {self.uri} unreachable: {exc}")
            self._last_check_status = False
            self._last_check_time = now
            return False
        except Exception as exc:
            logger.error(f"Unexpected error connecting to Neo4j: {exc}")
            self._last_check_status = False
            self._last_check_time = now
            return False

    def close(self):
        """Closes the underlying driver pool."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a read query and returns results as a list of dictionaries."""
        driver = self.get_driver()
        with driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a write query within an explicit managed write transaction."""
        driver = self.get_driver()

        def _write_tx(tx, q, p):
            res = tx.run(q, p)
            return [record.data() for record in res]

        with driver.session() as session:
            return session.execute_write(_write_tx, query, parameters or {})


neo4j_client = Neo4jClient()
