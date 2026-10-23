"""
Graph Projection and Contagion Intelligence Endpoints.
Provides graph synchronization, D3/PyVis network visualization data,
contagion path tracing, and counterparty concentration metrics.
"""

import uuid
from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_active_business
from app.models.entities import Business
from app.services.projection_service import ProjectionService
from app.graph.contagion import GraphContagionEngine
from app.schemas.api import GraphSyncResponse
from app.core.logging import logger

router = APIRouter(prefix="/graph", tags=["Graph"])


@router.post("/sync", response_model=GraphSyncResponse, summary="Synchronize Relational Data to Graph")
def sync_graph(
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> GraphSyncResponse:
    """Projects canonical PostgreSQL tables into Neo4j nodes and edges and refreshes NetworkX cache."""
    service = ProjectionService(db)
    counts = service.sync_all(business_id=business.id)
    total_nodes = sum(counts.values())
    return GraphSyncResponse(
        status="success",
        business_id=business.id,
        synced_nodes=total_nodes,
        synced_edges=total_nodes,
        message=f"Synchronized {total_nodes} nodes and relationships across {len(counts)} entity types."
    )


@router.get("/subgraph", response_model=Dict[str, Any], summary="Get Network Graph Visualization Data")
def get_graph_subgraph(
    entity_id: Optional[uuid.UUID] = Query(None, description="Optional entity UUID to focus 2-hop neighborhood"),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Returns PyVis and D3 compatible nodes and edges for rendering the business graph."""
    engine = GraphContagionEngine(db)
    center_id = str(entity_id) if entity_id else None
    return engine.get_entity_subgraph(business_id=business.id, center_node_id=center_id)


@router.get("/contagion-paths", response_model=List[Dict[str, Any]], summary="Trace Liquidity Contagion Paths")
def get_contagion_paths(
    as_of: Optional[date] = Query(None, description="Reference date for identifying overdue receivables"),
    horizon_days: int = Query(15, ge=1, le=60, description="Horizon to check upcoming obligation defaults"),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Traces causal chains from overdue customer receivables to impending loan/tax/supplier defaults."""
    calc_date = as_of or date.today()
    engine = GraphContagionEngine(db)
    return engine.trace_receivable_to_obligation_paths(
        business_id=business.id,
        as_of=calc_date,
        horizon_days=horizon_days
    )


@router.get("/concentrations", response_model=List[Dict[str, Any]], summary="Get Counterparty Concentration Ratios")
def get_concentrations(
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Calculates top customer receivable concentration percentages to flag counterparty risk."""
    engine = GraphContagionEngine(db)
    return engine.find_top_counterparty_concentrations(business_id=business.id)
