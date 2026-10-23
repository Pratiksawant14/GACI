"""
Frontend API Client.
Communicates with the FastAPI backend service to fetch deterministic financial data,
graph visualization structures, and AI agent explainability results.
"""

import sys
import os
from datetime import date
from typing import Dict, Any, List, Optional
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class ApiClient:
    """Client for FastAPI REST API endpoints."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.timeout = 30.0

    def check_health(self) -> Dict[str, Any]:
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=3.0)
            return resp.json() if resp.status_code == 200 else {"status": "unhealthy"}
        except Exception:
            return {"status": "offline"}

    def check_ready(self) -> Dict[str, Any]:
        try:
            resp = requests.get(f"{self.base_url}/ready", timeout=3.0)
            return resp.json() if resp.status_code == 200 else {"status": "degraded"}
        except Exception:
            return {"status": "offline", "database_connected": False, "neo4j_connected": False}

    def get_cash_summary(self, as_of: Optional[date] = None, business_id: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if as_of:
            params["as_of"] = as_of.isoformat()
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/analysis/cash-summary", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_blockages(self, as_of: Optional[date] = None, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if as_of:
            params["as_of"] = as_of.isoformat()
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/analysis/blockages", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_cash_projection(self, as_of: Optional[date] = None, horizon_days: int = 30, business_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"horizon_days": horizon_days}
        if as_of:
            params["as_of"] = as_of.isoformat()
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/analysis/cash-projection", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_aging_buckets(self, as_of: Optional[date] = None, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if as_of:
            params["as_of"] = as_of.isoformat()
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/analysis/aging-buckets", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_subgraph(self, business_id: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/graph/subgraph", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_contagion_paths(self, as_of: Optional[date] = None, horizon_days: int = 15, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"horizon_days": horizon_days}
        if as_of:
            params["as_of"] = as_of.isoformat()
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/graph/contagion-paths", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_concentrations(self, business_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if business_id:
            params["business_id"] = business_id
        resp = requests.get(f"{self.base_url}/api/v1/graph/concentrations", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def sync_graph(self, business_id: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if business_id:
            params["business_id"] = business_id
        resp = requests.post(f"{self.base_url}/api/v1/graph/sync", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def upload_file(self, file_name: str, file_bytes: bytes, table_type: Optional[str] = None, business_id: Optional[str] = None) -> Dict[str, Any]:
        files = [("files", (file_name, file_bytes, "text/csv"))]
        data = {}
        if table_type:
            data["table_type"] = table_type
        params = {}
        if business_id:
            params["business_id"] = business_id
        resp = requests.post(f"{self.base_url}/api/v1/ingest/upload", files=files, data=data, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def query_agent(self, query: str, as_of: Optional[date] = None, business_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"query": query}
        if as_of:
            payload["as_of"] = as_of.isoformat()
        if business_id:
            payload["business_id"] = business_id
        resp = requests.post(f"{self.base_url}/api/v1/agent/query", json=payload, timeout=45.0)
        resp.raise_for_status()
        return resp.json()

    def reset_database(self, business_id: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if business_id:
            params["business_id"] = business_id
        resp = requests.post(f"{self.base_url}/api/v1/ingest/reset", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_llm_health(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/api/v1/agent/llm-health", timeout=30.0)
        resp.raise_for_status()
        return resp.json()
