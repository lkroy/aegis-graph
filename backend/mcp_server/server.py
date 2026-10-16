"""AegisGraph MCP server: FalkorDB graph queries & algorithms as MCP tools.

Run standalone:
    python -m mcp_server.server            # stdio transport
    python -m mcp_server.server --sse       # SSE transport on MCP_PORT (default 8001)

The agent orchestrator invokes these tools through a real MCP ClientSession
(see mcp_server/client.py), so every graph operation travels the MCP
protocol - never a direct Python call in the agent loop.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from config import settings
from graph import cypher_queries as cq
from graph import shadow_simulator as sim
from graph.client import run_cypher

mcp = FastMCP("aegis-graph")


def _tool_result(cypher: str, result: Dict[str, Any]) -> str:
    """Standard JSON envelope: executed Cypher + rows + timing."""
    return json.dumps(
        {
            "cypher_executed": " ".join(cypher.split()),
            "rows": result.get("rows", []),
            "execution_time_ms": result.get("execution_time_ms"),
        }
    )


@mcp.tool()
def localize_root_cause(graph_name: str = "") -> str:
    """Run PageRank over :Service-[:CALLS] plus deepest-fault-boundary traversal
    to isolate the root-cause service, its active commit, and responsible engineer."""
    cypher, _ = cq.q("localize_root_cause")
    result = run_cypher(graph_name or settings.prod_graph, cypher)
    return _tool_result(cypher, result)


@mcp.tool()
def compute_blast_radius(graph_name: str, target_service_id: str) -> str:
    """Multi-hop blast radius: which :BusinessFlow SLAs depend on the target
    service, with the ordered causal proof path for each flow."""
    cypher, _ = cq.q("blast_radius")
    result = run_cypher(
        graph_name or settings.prod_graph, cypher, {"target_service_id": target_service_id}
    )
    return _tool_result(cypher, result)


@mcp.tool()
def detect_shared_bottleneck(graph_name: str, db_id: str) -> str:
    """Degree analysis over [:READS_WRITES]: rank services by connections held
    on a database to find the noisy neighbor behind pool exhaustion."""
    cypher, _ = cq.q("bottleneck_analysis")
    result = run_cypher(graph_name or settings.prod_graph, cypher, {"db_id": db_id})
    return _tool_result(cypher, result)


@mcp.tool()
def discover_failover_route(graph_name: str, source_id: str, target_id: str) -> str:
    """shortestPath failover discovery between two services, avoiding
    DOWN/OFFLINE nodes."""
    cypher, _ = cq.q("failover_route")
    result = run_cypher(
        graph_name or settings.prod_graph,
        cypher,
        {"source_id": source_id, "target_id": target_id},
    )
    return _tool_result(cypher, result)


@mcp.tool()
def simulate_candidate_action(
    action_code: str, params_json: str = "{}", sim_name: str = ""
) -> str:
    """Shadow-graph duel: clone prod_graph into an isolated shadow graph,
    apply the candidate mutation, verify :BusinessFlow SLA reachability.

    action_code: KILL_AND_ISOLATE_NODE | ROLLBACK_COMMIT |
                 THROTTLE_NOISY_NEIGHBOR | ACTIVATE_FALLBACK_ROUTE
    params_json: e.g. {"target_service_id": "fx-rate-service", "commit_id": "commit-9f82a"}
    sim_name: target shadow graph (defaults to sim_<action>_<hash>).
    Returns APPROVED/REJECTED verdict with orphaned flows and revenue impact.
    """
    params: Dict[str, Any] = json.loads(params_json or "{}")
    name = sim_name or f"sim_{action_code.lower()}_{abs(hash(params_json)) % 10000}"
    verdict = sim.simulate(action_code, name, **params)
    return json.dumps(verdict)


@mcp.tool()
def recall_similar_incidents(scenario_key: Optional[str] = None, limit: int = 5) -> str:
    """Track 02 episodic memory: recall past :IncidentEpisode nodes from
    FalkorDB matching a failure signature, newest first."""
    cypher, _ = cq.q("recall_episodes")
    result = run_cypher(
        settings.prod_graph, cypher, {"scenario_key": scenario_key, "limit": limit}
    )
    return _tool_result(cypher, result)


@mcp.tool()
def list_graphs() -> str:
    """List available FalkorDB graphs (prod + shadow inspection graphs)."""
    from graph.client import list_graphs as _list

    return json.dumps({"graphs": _list()})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sse", action="store_true", help="Run with SSE transport")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.sse:
        mcp.run(transport="sse")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
