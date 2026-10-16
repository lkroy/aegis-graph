"""FalkorDB connection and multigraph helpers.

Every read/write in AegisGraph goes through this module so that all graph
work executes as real Cypher against a live FalkorDB instance - never in
Python-side mocks or dicts.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from falkordb import FalkorDB

from config import settings


_db: Optional[FalkorDB] = None


def get_db() -> FalkorDB:
    """Return a shared FalkorDB client (lazy singleton)."""
    global _db
    if _db is None:
        kwargs: Dict[str, Any] = {
            "host": settings.falkor_host,
            "port": settings.falkor_port,
        }
        if settings.falkor_username:
            kwargs["username"] = settings.falkor_username
        if settings.falkor_password:
            kwargs["password"] = settings.falkor_password
        _db = FalkorDB(**kwargs)
    return _db


def graph(name: Optional[str] = None):
    """Select a named graph (FalkorDB multigraph topology)."""
    return get_db().select_graph(name or settings.prod_graph)


def list_graphs() -> List[str]:
    try:
        return list(get_db().list_graphs())
    except Exception:
        return []


def delete_graph(name: str) -> None:
    try:
        graph(name).delete()
    except Exception:
        pass


def run_cypher(graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute Cypher against a named graph and return rows + timing.

    Returns: {"rows": [...], "execution_time_ms": float}
    """
    g = graph(graph_name)
    start = time.perf_counter()
    result = g.query(cypher, params or {})
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    rows: List[Dict[str, Any]] = []
    try:
        # header is a list of [type_code, column_name] pairs.
        header = [h[1] if isinstance(h, (list, tuple)) else h
                  for h in (result.header or [])]
    except Exception:
        header = []
    for record in result.result_set or []:
        row: Dict[str, Any] = {}
        for idx, col in enumerate(header):
            val = record[idx] if idx < len(record) else None
            row[col] = _jsonable(val)
        rows.append(row)
    return {"rows": rows, "execution_time_ms": round(elapsed_ms, 3)}


def _jsonable(value: Any) -> Any:
    """Convert FalkorDB driver types (Node/Edge/Path) into plain JSON."""
    # Import locally to avoid hard dependency at module import time.
    try:
        from falkordb import Node as FalkorNode, Edge as FalkorEdge, Path as FalkorPath
    except Exception:  # pragma: no cover
        FalkorNode = FalkorEdge = FalkorPath = ()  # type: ignore

    if FalkorNode and isinstance(value, FalkorNode):
        return {
            "id": getattr(value, "id", None),
            "labels": list(getattr(value, "labels", []) or []),
            "properties": dict(getattr(value, "properties", {}) or {}),
        }
    if FalkorEdge and isinstance(value, FalkorEdge):
        return {
            "id": getattr(value, "id", None),
            "type": getattr(value, "relation", None) or getattr(value, "type", None),
            "properties": dict(getattr(value, "properties", {}) or {}),
        }
    if FalkorPath and isinstance(value, FalkorPath):
        nodes = getattr(value, "nodes", []) or []
        return [getattr(n, "id", None) for n in nodes]
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def wait_for_falkor(timeout_s: int = 30) -> bool:
    """Block until FalkorDB answers, or timeout. Used at backend startup."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            get_db().select_graph("__health__").query("RETURN 1 AS ok")
            return True
        except Exception:
            time.sleep(1.0)
    return False
