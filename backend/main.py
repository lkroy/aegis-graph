"""AegisGraph FastAPI server: REST + WebSocket for the SRE command center.

Endpoints:
  GET  /api/graph?graph_name=prod_graph
  POST /api/reset
  POST /api/chaos/{scenario_id}
  POST /api/agent/remediate
  GET  /api/episodes
  WS   /ws/agent
"""
from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.orchestrator import run_remediation, run_remediation_collect
from config import settings
from graph import chaos_engine, cypher_queries as cq, seed_topology
from graph.client import list_graphs, run_cypher, wait_for_falkor


def _start_mcp_server() -> None:
    """Run the FastMCP SSE server in a daemon thread (real MCP transport)."""
    import uvicorn

    from mcp_server.server import mcp

    app = mcp.sse_app()
    thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": "127.0.0.1", "port": 8001, "log_level": "warning"},
        daemon=True,
    )
    thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not wait_for_falkor(timeout_s=30):
        print("WARNING: FalkorDB not reachable; API will serve errors.")
    else:
        if settings.auto_seed:
            existing = run_cypher(
                settings.prod_graph, "MATCH (n) RETURN count(n) AS c"
            )["rows"]
            if not existing or existing[0].get("c", 0) == 0:
                counts = seed_topology.seed()
                print(f"Seeded prod_graph: {counts}")
    _start_mcp_server()
    # Give the MCP SSE server a moment to bind before agent calls arrive.
    await asyncio.sleep(1.5)
    yield


app = FastAPI(title="AegisGraph", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RemediateRequest(BaseModel):
    scenario_id: str


def _metrics(graph_name: str) -> Dict[str, Any]:
    res = run_cypher(
        graph_name,
        """
        MATCH (bf:BusinessFlow)
        WITH sum(CASE WHEN bf.status IN ['AT_RISK', 'DOWN'] THEN bf.revenue_per_min ELSE 0 END)
             AS revenue_at_risk
        OPTIONAL MATCH (s:Service)
        WHERE s.status IN ['DEGRADED', 'DOWN', 'OFFLINE']
        WITH revenue_at_risk, count(s) AS degraded
        OPTIONAL MATCH (ep:IncidentEpisode)
        RETURN revenue_at_risk, degraded, count(ep) AS episodes
        """,
    )
    row = (res["rows"] or [{}])[0]
    return {
        "revenue_at_risk_per_min": row.get("revenue_at_risk", 0),
        "degraded_nodes": row.get("degraded", 0),
        "episodic_memories": row.get("episodes", 0),
    }


@app.get("/api/graph")
def get_graph(graph_name: str = "prod_graph") -> Dict[str, Any]:
    data = cq.serialize_graph(graph_name)
    return {"graph_name": graph_name, **data, "metrics": _metrics(graph_name),
            "available_graphs": list_graphs()}


@app.post("/api/reset")
def reset() -> Dict[str, Any]:
    from graph import shadow_simulator as sim

    counts = seed_topology.seed()
    sim.cleanup_shadows(keep_pinned=True)
    return {"status": "reset", **counts, "metrics": _metrics(settings.prod_graph)}


@app.post("/api/chaos/{scenario_id}")
def inject_chaos(scenario_id: str) -> Dict[str, Any]:
    # Reset to a clean slate first so scenarios are deterministic.
    seed_topology.seed()
    from graph import shadow_simulator as sim

    sim.cleanup_shadows(keep_pinned=True)
    info = chaos_engine.inject(scenario_id)
    data = cq.serialize_graph(settings.prod_graph)
    return {"scenario": info, "alerts": chaos_engine.active_alerts(),
            "metrics": _metrics(settings.prod_graph), **data}


@app.post("/api/agent/remediate")
async def remediate(req: RemediateRequest) -> Dict[str, Any]:
    trace = await run_remediation_collect(req.scenario_id)
    data = cq.serialize_graph(settings.prod_graph)
    return {"scenario_id": req.scenario_id, "trace": trace,
            "metrics": _metrics(settings.prod_graph), **data}


@app.get("/api/episodes")
def episodes() -> Dict[str, Any]:
    res = cq.recall_episodes(settings.prod_graph, limit=25)
    return {"episodes": res["rows"]}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    ok = wait_for_falkor(timeout_s=3)
    return {"status": "ok" if ok else "degraded", "falkor_reachable": ok,
            "graphs": list_graphs()}


@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {}
            scenario_id = msg.get("scenario_id", "poison_pill_commit")
            if msg.get("action") == "remediate":
                async for event in run_remediation(scenario_id):
                    await ws.send_text(json.dumps(event))
                # Send the final refreshed graph + metrics.
                data = cq.serialize_graph(settings.prod_graph)
                await ws.send_text(json.dumps(
                    {"phase": "DONE", "metrics": _metrics(settings.prod_graph),
                     "nodes": data["nodes"], "links": data["links"]}))
            else:
                await ws.send_text(json.dumps({"error": "unknown action"}))
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=False)
