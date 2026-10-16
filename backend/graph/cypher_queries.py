"""All Cypher queries and FalkorDB graph-algorithm calls used by AegisGraph.

Each function returns (cypher, params). The *_run helpers execute against a
named graph and return rows + timing via graph.client.run_cypher.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from graph.client import run_cypher

# ----------------------------------------------------------------------------
# 1. Full graph serialization for the UI canvas
# ----------------------------------------------------------------------------

SERIALIZE_GRAPH = """
MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
RETURN collect(DISTINCT {
  id: n.id,
  label: labels(n)[0],
  name: coalesce(n.name, n.hash, n.handle, n.title, n.id),
  status: coalesce(n.status, 'HEALTHY'),
  props: properties(n)
}) AS nodes,
collect(DISTINCT {
  source: n.id,
  target: m.id,
  type: type(r),
  props: properties(r)
}) AS links
"""


def serialize_graph(graph_name: str) -> Dict[str, Any]:
    res = run_cypher(graph_name, SERIALIZE_GRAPH)
    rows = res["rows"]
    payload = rows[0] if rows else {"nodes": [], "links": []}
    # Filter the null-link row produced by the OPTIONAL MATCH on edgeless nodes.
    links = [lnk for lnk in (payload.get("links") or []) if lnk.get("target")]
    return {
        "nodes": payload.get("nodes") or [],
        "links": links,
        "execution_time_ms": res["execution_time_ms"],
    }


# ----------------------------------------------------------------------------
# 2. Root-cause localization: PageRank over CALLS + deepest fault boundary
# ----------------------------------------------------------------------------

LOCALIZE_ROOT_CAUSE = """
CALL algo.pageRank('Service', 'CALLS') YIELD node, score
WITH node AS svc, score
WHERE svc.status IN ['DEGRADED', 'DOWN']
OPTIONAL MATCH (svc)-[:CALLS {route_type: 'PRIMARY'}]->(downstream:Service)
WHERE downstream.status IN ['DEGRADED', 'DOWN']
WITH svc, score, count(downstream) AS failing_children
OPTIONAL MATCH (svc)-[:READS_WRITES]->(db:Database)
WHERE db.status IN ['SATURATED', 'DOWN']
OPTIONAL MATCH (c:Commit {is_active: true})-[:DEPLOYED_TO]->(svc)
OPTIONAL MATCH (eng:Engineer)-[:AUTHORED]->(c)
OPTIONAL MATCH (owner:Engineer)-[:OWNS_SERVICE]->(svc)
OPTIONAL MATCH (rb:Runbook)-[:GOVERNS]->(svc)
RETURN svc.id AS service_id,
       svc.name AS service_name,
       svc.status AS status,
       svc.error_rate AS error_rate,
       svc.latency_ms AS latency_ms,
       score AS pagerank_score,
       failing_children AS failing_children,
       db.id AS bottleneck_db_id,
       db.status AS db_status,
       db.active_conns AS db_active_conns,
       c.id AS active_commit_id,
       c.hash AS commit_hash,
       c.message AS commit_message,
       coalesce(eng.handle, owner.handle) AS responsible_engineer,
       rb.id AS runbook_id,
       rb.action_code AS recommended_runbook_action
ORDER BY failing_children ASC, svc.error_rate DESC, score DESC
LIMIT 3
"""


def localize_root_cause(graph_name: str) -> Dict[str, Any]:
    return run_cypher(graph_name, LOCALIZE_ROOT_CAUSE)


# ----------------------------------------------------------------------------
# 3. Multi-hop blast radius + causal proof path extraction
# ----------------------------------------------------------------------------

BLAST_RADIUS = """
MATCH path = (bf:BusinessFlow)-[:DEPENDS_ON]->(entry:Service)-[:CALLS*0..6]->(target:Service {id: $target_service_id})
WHERE ALL(r IN relationships(path) WHERE type(r) = 'DEPENDS_ON' OR r.route_type = 'PRIMARY')
RETURN bf.id AS flow_id,
       bf.name AS flow_name,
       bf.revenue_per_min AS revenue_per_min,
       [n IN nodes(path) | n.id] AS causal_node_path,
       length(path) AS hops
"""


def blast_radius(graph_name: str, target_service_id: str) -> Dict[str, Any]:
    return run_cypher(graph_name, BLAST_RADIUS, {"target_service_id": target_service_id})


# ----------------------------------------------------------------------------
# 4. Shared bottleneck detection (degree analysis over READS_WRITES)
# ----------------------------------------------------------------------------

BOTTLENECK_ANALYSIS = """
MATCH (db:Database {id: $db_id})<-[r:READS_WRITES]-(caller:Service)
OPTIONAL MATCH (owner:Engineer)-[:OWNS_SERVICE]->(caller)
RETURN caller.id AS service_id,
       caller.tier AS tier,
       r.conn_weight AS connections_held,
       owner.handle AS owner_handle
ORDER BY r.conn_weight DESC
"""


def bottleneck_analysis(graph_name: str, db_id: str) -> Dict[str, Any]:
    return run_cypher(graph_name, BOTTLENECK_ANALYSIS, {"db_id": db_id})


# ----------------------------------------------------------------------------
# 5. Healthy failover route discovery via shortestPath
# ----------------------------------------------------------------------------

FAILOVER_ROUTE = """
MATCH (src:Service {id: $source_id}), (dst:Service {id: $target_id})
WITH src, dst, shortestPath((src)-[:CALLS*1..6]->(dst)) AS p
WHERE p IS NOT NULL
  AND NONE(n IN nodes(p) WHERE n.status IN ['DOWN', 'OFFLINE'])
RETURN [n IN nodes(p) | n.id] AS failover_path,
       length(p) AS hops
"""


def failover_route(graph_name: str, source_id: str, target_id: str) -> Dict[str, Any]:
    return run_cypher(
        graph_name, FAILOVER_ROUTE, {"source_id": source_id, "target_id": target_id}
    )


# ----------------------------------------------------------------------------
# 6. SLA reachability verification (run inside a shadow graph after mutation)
#
# A BusinessFlow is reachable iff no service in its PRIMARY transitive
# closure blocks traffic. A non-HEALTHY service does NOT block when its
# parent has a FALLBACK edge to a HEALTHY alternative (failover bypass).
# ----------------------------------------------------------------------------

SLA_VERIFY = """
MATCH (bf:BusinessFlow)-[:DEPENDS_ON]->(entry:Service)
OPTIONAL MATCH p = (entry)-[:CALLS*0..6]->(s:Service)
WHERE ALL(r IN relationships(p) WHERE r.route_type = 'PRIMARY')
WITH bf, collect(DISTINCT s) AS closure
OPTIONAL MATCH (parent:Service)-[pr:CALLS]->(blocked:Service)
WHERE pr.route_type = 'PRIMARY'
  AND blocked IN closure
  AND blocked.status IN ['DEGRADED', 'DOWN', 'OFFLINE']
  AND NOT (parent)-[:CALLS {route_type: 'FALLBACK'}]->(:Service {status: 'HEALTHY'})
WITH bf, collect(DISTINCT blocked.id) AS blockers
RETURN bf.id AS flow_id,
       bf.name AS flow_name,
       bf.revenue_per_min AS revenue_per_min,
       size(blockers) = 0 AS reachable,
       blockers AS blocking_services
"""


def verify_slas(graph_name: str) -> Dict[str, Any]:
    """Return orphaned flows + projected revenue loss for a (shadow) graph."""
    res = run_cypher(graph_name, SLA_VERIFY)
    orphaned = [r["flow_id"] for r in res["rows"] if not r["reachable"]]
    loss = sum(r["revenue_per_min"] for r in res["rows"] if not r["reachable"])
    blockers = {r["flow_id"]: r.get("blocking_services") or [] for r in res["rows"]}
    return {
        "orphaned_flows": orphaned,
        "blocking_services": blockers,
        "projected_revenue_loss_per_min": loss,
        "simulation_passed": len(orphaned) == 0,
        "execution_time_ms": res["execution_time_ms"],
    }


HEAL_FLOWS = """
MATCH (bf:BusinessFlow)-[:DEPENDS_ON]->(entry:Service)
OPTIONAL MATCH p = (entry)-[:CALLS*0..6]->(s:Service)
WHERE ALL(r IN relationships(p) WHERE r.route_type = 'PRIMARY')
WITH bf, collect(DISTINCT s) AS closure
OPTIONAL MATCH (parent:Service)-[pr:CALLS]->(blocked:Service)
WHERE pr.route_type = 'PRIMARY'
  AND blocked IN closure
  AND blocked.status IN ['DEGRADED', 'DOWN', 'OFFLINE']
  AND NOT (parent)-[:CALLS {route_type: 'FALLBACK'}]->(:Service {status: 'HEALTHY'})
WITH bf, collect(DISTINCT blocked.id) AS blockers
WHERE size(blockers) = 0 AND bf.status IN ['AT_RISK', 'DOWN']
SET bf.status = 'HEALTHY'
RETURN count(bf) AS healed_flows
"""


def heal_flows(graph_name: str) -> Dict[str, Any]:
    """Restore BusinessFlows whose dependency closure is fully healthy."""
    return run_cypher(graph_name, HEAL_FLOWS)


# ----------------------------------------------------------------------------
# 7. Episodic memory recall (Track 02)
# ----------------------------------------------------------------------------

RECALL_EPISODES = """
MATCH (ep:IncidentEpisode)
WHERE ep.scenario_key = $scenario_key OR $scenario_key IS NULL
OPTIONAL MATCH (ep)-[:RESOLVED_TARGET]->(t:Service)
RETURN ep.id AS episode_id,
       ep.scenario_key AS scenario_key,
       ep.root_cause_node AS root_cause_node,
       ep.approved_action AS approved_action,
       ep.rejected_action AS rejected_action,
       ep.causal_path_json AS causal_path_json,
       ep.resolved_at AS resolved_at,
       t.id AS resolved_target
ORDER BY ep.resolved_at DESC
LIMIT $limit
"""


def recall_episodes(graph_name: str, scenario_key: str | None = None, limit: int = 10) -> Dict[str, Any]:
    return run_cypher(
        graph_name, RECALL_EPISODES, {"scenario_key": scenario_key, "limit": limit}
    )


def q(name: str) -> Tuple[str, Dict[str, Any]]:
    """Return (cypher, empty_params) for a named query - used by the MCP server."""
    queries = {
        "localize_root_cause": (LOCALIZE_ROOT_CAUSE, {}),
        "blast_radius": (BLAST_RADIUS, {}),
        "bottleneck_analysis": (BOTTLENECK_ANALYSIS, {}),
        "failover_route": (FAILOVER_ROUTE, {}),
        "sla_verify": (SLA_VERIFY, {}),
        "recall_episodes": (RECALL_EPISODES, {}),
        "serialize": (SERIALIZE_GRAPH, {}),
    }
    return queries[name]
