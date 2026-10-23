"""
API Request and Response Schemas.
Pydantic v2 models for API endpoint inputs and standardized responses.
"""

import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    environment: str
    version: str = "1.0.0"


class ReadinessResponse(BaseModel):
    status: str
    database_connected: bool
    neo4j_connected: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class IngestionSummaryResponse(BaseModel):
    business_id: uuid.UUID
    business_name: str
    reports: List[Dict[str, Any]]
    total_files_processed: int
    graph_synced: bool


class GraphSyncResponse(BaseModel):
    status: str
    business_id: uuid.UUID
    synced_nodes: int
    synced_edges: int
    message: str
