"""Shadow-graph simulator (FalkorDB multigraph isolation).

Before the agent touches production, it clones prod_graph into an isolated
shadow graph (sim_graph_<id>), applies a candidate mutation there, and runs
SLA reachability Cypher to prove zero collateral damage to :BusinessFlow SLAs.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from config import settings
from graph import cypher_queries as cq
from graph.client import delete_graph, graph, list_graphs, run_cypher

# Shadow graphs the UI keeps alive for inspection.
PINNED_SHADOWS = ("sim_rejected", "sim_approved")


def clone_prod_to_shadow(sim_name: str) -> Dict[str, Any]:
    """Clone every node+edge of prod_graph into sim_name.

    Nodes are recreated with explicit labels (no apoc in FalkorDB). All
    AegisGraph addressing uses the business `id` property, so internal node
    ids do not need to round-trip.
    """
    start = time.perf_counter()
    delete_graph(sim_name)
    src = graph(settings.prod_graph)
    dst = graph(sim_name)

    nodes = src.query(
        "MATCH (n) RETURN labels(n) AS _labels, properties(n) AS _props"
    ).result_set
    by_label: Dict[str, List[Dict[str, Any]]] = {}
    for r in (nodes or []):
        labels = list(r[0])
        label = labels[0] if labels else ""
        props = {k: v for k, v in dict(r[1]).items() if not k.startswith("_")}
        by_label.setdefault(label, []).append(props)
    for label, rows in by_label.items():
        if not label:
            continue
        dst.query(f"UNWIND $rows AS row CREATE (n:{label}) SET n = row",
                  {"rows": rows})

    edges = src.query(
        "MATCH (a)-[r]->(b) RETURN a.id AS src, b.id AS dst, "
        "type(r) AS rel, properties(r) AS props"
    ).result_set
    edge_rows = [
        {"src": r[0], "dst": r[1], "rel": r[2], "props": dict(r[3])}
        for r in (edges or [])
    ]
    for erow in edge_rows:
        props = {k: v for k, v in erow["props"].items() if not k.startswith("_")}
        set_clause = (
            " SET r = $props" if props else ""
        )
        dst.query(
            f"MATCH (a {{id: $src}}), (b {{id: $dst}}) "
            f"CREATE (a)-[r:{erow['rel']}]->(b){set_clause}",
            {"src": erow["src"], "dst": erow["dst"], "props": props},
        )

    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
    counts = run_cypher(
        sim_name,
        "MATCH (n) WITH count(n) AS nodes MATCH ()-[r]->() RETURN nodes, count(r) AS edges",
    )["rows"][0]
    return {
        "shadow_graph": sim_name,
        "nodes": counts["nodes"],
        "edges": counts["edges"],
        "clone_time_ms": elapsed_ms,
    }


# ----------------------------------------------------------------------------
# Candidate action mutations (applied inside a shadow graph only)
# ----------------------------------------------------------------------------

def kill_and_isolate_node(sim_name: str, target_service_id: str) -> None:
    run_cypher(
        sim_name,
        """
        MATCH (t:Service {id: $target})
        SET t.status = 'OFFLINE', t.error_rate = 1.0
        WITH t
        MATCH (:Service)-[r:CALLS]->(t)
        DELETE r
        """,
        {"target": target_service_id},
    )


def rollback_commit(sim_name: str, target_service_id: str, commit_id: str) -> None:
    run_cypher(
        sim_name,
        """
        MATCH (c:Commit {id: $commit})-[:DEPLOYED_TO]->(t:Service {id: $target})
        SET c.is_active = false
        SET t.status = 'HEALTHY', t.error_rate = 0.01
        """,
        {"commit": commit_id, "target": target_service_id},
    )
    # Propagate health upstream where no other downstream fault exists.
    run_cypher(
        sim_name,
        """
        MATCH (up:Service)-[:CALLS]->(:Service)
        WHERE up.status IN ['DEGRADED', 'DOWN']
        WITH up
        OPTIONAL MATCH (up)-[:CALLS]->(other:Service)
        WHERE other.status IN ['DEGRADED', 'DOWN', 'OFFLINE']
        WITH up, count(other) AS bad_downstream
        WHERE bad_downstream = 0
        SET up.status = 'HEALTHY', up.error_rate = 0.01
        """,
        {"target": target_service_id},
    )
    _cascade_heal(sim_name)


def throttle_noisy_neighbor(sim_name: str, hog_service_id: str, db_id: str) -> None:
    run_cypher(
        sim_name,
        """
        MATCH (hog:Service {id: $hog})-[r:READS_WRITES]->(db:Database {id: $db})
        SET r.conn_weight = 10,
            db.status = 'HEALTHY',
            db.active_conns = 180
        """,
        {"hog": hog_service_id, "db": db_id},
    )
    run_cypher(
        sim_name,
        """
        MATCH (s:Service)-[:READS_WRITES]->(db:Database {id: $db})
        WHERE s.status = 'DEGRADED'
        SET s.status = 'HEALTHY', s.error_rate = 0.01
        """,
        {"db": db_id},
    )


def activate_fallback_route(
    sim_name: str, parent_service_id: str, failed_service_id: str, fallback_service_id: str
) -> None:
    run_cypher(
        sim_name,
        """
        MATCH (parent:Service {id: $parent})-[r:CALLS]->(fb:Service {id: $fallback})
        SET r.route_type = 'PRIMARY'
        WITH parent
        MATCH (parent)-[r2:CALLS]->(failed:Service {id: $failed})
        SET r2.route_type = 'FALLBACK'
        """,
        {"parent": parent_service_id, "fallback": fallback_service_id, "failed": failed_service_id},
    )
    run_cypher(
        sim_name,
        "MATCH (s:Service {id: $parent}) SET s.status = 'HEALTHY', s.error_rate = 0.01",
        {"parent": parent_service_id},
    )
    _cascade_heal(sim_name)


def _cascade_heal(sim_name: str) -> None:
    """Iteratively restore upstream services whose downstream faults are gone."""
    for _ in range(6):
        res = run_cypher(
            sim_name,
            """
            MATCH (up:Service)-[:CALLS]->(:Service)
            WHERE up.status IN ['DEGRADED', 'DOWN']
            WITH up
            OPTIONAL MATCH (up)-[:CALLS]->(other:Service)
            WHERE other.status IN ['DEGRADED', 'DOWN', 'OFFLINE']
            WITH up, count(other) AS bad_downstream
            WHERE bad_downstream = 0
            SET up.status = 'HEALTHY', up.error_rate = 0.01
            RETURN count(up) AS healed
            """,
        )
        if not res["rows"] or res["rows"][0].get("healed", 0) == 0:
            break


MUTATIONS = {
    "KILL_AND_ISOLATE_NODE": kill_and_isolate_node,
    "ROLLBACK_COMMIT": rollback_commit,
    "THROTTLE_NOISY_NEIGHBOR": throttle_noisy_neighbor,
    "ACTIVATE_FALLBACK_ROUTE": activate_fallback_route,
}


def simulate(
    action_code: str, sim_name: str, **kwargs: Any
) -> Dict[str, Any]:
    """Clone prod -> shadow, apply mutation, verify SLAs. Returns the verdict."""
    clone_info = clone_prod_to_shadow(sim_name)
    MUTATIONS[action_code](sim_name, **kwargs)
    sla = cq.verify_slas(sim_name)
    return {
        "action": action_code,
        "params": kwargs,
        "shadow_graph": sim_name,
        "clone_time_ms": clone_info["clone_time_ms"],
        "verdict": "APPROVED" if sla["simulation_passed"] else "REJECTED",
        **sla,
    }


def cleanup_shadows(keep_pinned: bool = True) -> List[str]:
    """Delete scratch shadow graphs, keeping the two pinned inspection graphs."""
    removed = []
    for name in list_graphs():
        if name.startswith("sim_") and not (keep_pinned and name in PINNED_SHADOWS):
            delete_graph(name)
            removed.append(name)
    return removed
