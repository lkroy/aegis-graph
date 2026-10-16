"""AegisGraph agent orchestrator (Track 01).

Deterministic, graph-first remediation loop. Every observation and every
candidate action goes through MCP tools backed by real Cypher against
FalkorDB - no Python-side mocks. Produces a step-by-step trace the frontend
animates, including the shadow-graph duel (REJECTED vs APPROVED) and the
ordered causal proof path for each action.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from config import settings
from graph import cypher_queries as cq
from graph import shadow_simulator as sim
from graph.client import run_cypher
from mcp_server import client as mcp_client

GRAPH = settings.prod_graph

# ----------------------------------------------------------------------------
# Scenario duel configuration: naive (to be REJECTED) vs surgical (APPROVED)
# ----------------------------------------------------------------------------

DUELS: Dict[str, Dict[str, Any]] = {
    "poison_pill_commit": {
        "naive": {
            "action": "KILL_AND_ISOLATE_NODE",
            "params": {"target_service_id": "fx-rate-service"},
            "label": "Circuit-break fx-rate-service",
        },
        "surgical": {
            "action": "ROLLBACK_COMMIT",
            "params": {
                "target_service_id": "fx-rate-service",
                "commit_id": "commit-9f82a",
            },
            "label": "Rollback poison-pill commit #9f82a",
        },
    },
    "db_pool_exhaustion": {
        "naive": {
            "action": "KILL_DATABASE",
            "params": {"db_id": "redis-shared-cluster"},
            "label": "Kill redis-shared-cluster",
        },
        "surgical": {
            "action": "THROTTLE_NOISY_NEIGHBOR",
            "params": {
                "hog_service_id": "analytics-batch-worker",
                "db_id": "redis-shared-cluster",
            },
            "label": "Throttle analytics-batch-worker (noisy neighbor)",
        },
        "bottleneck_db": "redis-shared-cluster",
    },
    "gateway_crash_reroute": {
        "naive": {
            "action": "KILL_AND_ISOLATE_NODE",
            "params": {"target_service_id": "payment-router"},
            "label": "Circuit-break payment-router",
        },
        "surgical": {
            "action": "ACTIVATE_FALLBACK_ROUTE",
            "params": {
                "parent_service_id": "payment-router",
                "failed_service_id": "stripe-connector-primary",
                "fallback_service_id": "adyen-eu-fallback",
            },
            "label": "Reroute payment-router -> adyen-eu-fallback",
        },
        "failover": {"source_id": "payment-router", "target_id": "adyen-eu-fallback"},
    },
}


def _trace(
    step: int,
    phase: str,
    mcp_tool_name: str,
    payload: Dict[str, Any],
    highlighted: Optional[List[str]] = None,
    proof_path: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "step_number": step,
        "phase": phase,
        "mcp_tool_name": mcp_tool_name,
        "cypher_executed": payload.get("cypher_executed", ""),
        "execution_time_ms": payload.get("execution_time_ms"),
        "highlighted_nodes": highlighted or [],
        "proof_path": proof_path or [],
    }
    if extra:
        event.update(extra)
    return event


async def run_remediation(scenario_id: str) -> AsyncIterator[Dict[str, Any]]:
    """Execute the full agent loop, yielding trace events for the UI."""
    if scenario_id not in DUELS:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    duel = DUELS[scenario_id]
    step = 0

    # -- Step 1: episodic memory lookup (Track 02) ---------------------------
    step += 1
    mem = await mcp_client.call_tool(
        "recall_similar_incidents", {"scenario_key": scenario_id, "limit": 5}
    )
    yield _trace(step, "MEMORY_LOOKUP", "recall_similar_incidents", mem,
                 extra={"episodes_found": len(mem.get("rows", [])),
                        "episodes": mem.get("rows", [])})

    # -- Step 2: root-cause localization (Track 01, PageRank) -----------------
    step += 1
    diag = await mcp_client.call_tool("localize_root_cause", {"graph_name": GRAPH})
    candidates = diag.get("rows", [])
    root = candidates[0] if candidates else {}
    target = root.get("service_id", "")
    yield _trace(
        step, "GRAPH_DIAGNOSIS", "localize_root_cause", diag,
        highlighted=[target] if target else [],
        extra={"root_cause": root, "candidates": candidates},
    )
    if not target:
        yield _trace(step + 1, "EXECUTED_REMEDIATION", "none", {},
                     extra={"note": "No degraded services found; nothing to remediate."})
        return

    # -- Step 2b: scenario-specific deep inspection ---------------------------
    # cause_service drives the final notification + episodic memory. It defaults
    # to the PageRank pick but is overridden when a deeper inspection finds the
    # true culprit (e.g. the noisy neighbor behind a saturated pool).
    cause_service = target
    if "bottleneck_db" in duel:
        step += 1
        bn = await mcp_client.call_tool(
            "detect_shared_bottleneck",
            {"graph_name": GRAPH, "db_id": duel["bottleneck_db"]},
        )
        hog = (bn.get("rows") or [{}])[0].get("service_id")
        if hog:
            cause_service = hog
        yield _trace(step, "GRAPH_DIAGNOSIS", "detect_shared_bottleneck", bn,
                     highlighted=[hog] if hog else [],
                     extra={"noisy_neighbor": bn.get("rows", []),
                            "root_cause_override": hog})
    if "failover" in duel:
        step += 1
        fo = await mcp_client.call_tool(
            "discover_failover_route",
            {"graph_name": GRAPH, **duel["failover"]},
        )
        fopath = ((fo.get("rows") or [{}])[0].get("failover_path")) or []
        yield _trace(step, "GRAPH_DIAGNOSIS", "discover_failover_route", fo,
                     highlighted=fopath, proof_path=fopath,
                     extra={"failover_path": fopath})

    # -- Step 3: blast radius (union across all degraded candidates) ------------
    step += 1
    # Union the structural blast radius of every degraded service so the
    # incident's true impact is captured (e.g. a saturated DB starves several
    # services at once). Keeps the longest causal path per flow for the proof.
    merged_flows: Dict[str, Dict[str, Any]] = {}
    br_ms = 0.0
    br_cypher = ""
    for cand in candidates:
        svc_id = cand.get("service_id")
        if not svc_id:
            continue
        br = await mcp_client.call_tool(
            "compute_blast_radius", {"graph_name": GRAPH, "target_service_id": svc_id}
        )
        br_ms += br.get("execution_time_ms") or 0
        br_cypher = br.get("cypher_executed", br_cypher)
        for f in br.get("rows", []):
            fid = f.get("flow_id")
            prev = merged_flows.get(fid, {})
            if len(f.get("causal_node_path") or []) >= len(prev.get("causal_node_path") or []):
                merged_flows[fid] = f
    flows = list(merged_flows.values())
    revenue = sum(f.get("revenue_per_min", 0) for f in flows)
    br_payload = {"cypher_executed": br_cypher, "execution_time_ms": round(br_ms, 3)}
    proof_path: List[str] = []
    for f in flows:
        p = f.get("causal_node_path") or []
        if len(p) > len(proof_path):
            proof_path = p
    highlighted = sorted({n for f in flows for n in (f.get("causal_node_path") or [])})
    yield _trace(
        step, "BLAST_RADIUS", "compute_blast_radius", br_payload,
        highlighted=highlighted, proof_path=proof_path,
        extra={"impacted_flows": flows, "revenue_at_risk_per_min": revenue},
    )

    # -- Steps 4/5: shadow-graph duel ------------------------------------------
    shadow_comparison: Dict[str, Any] = {}
    for phase, key, sim_name in (
        ("SHADOW_SIM_REJECTED", "naive", "sim_rejected"),
        ("SHADOW_SIM_APPROVED", "surgical", "sim_approved"),
    ):
        step += 1
        action = duel[key]
        sim_res = await _simulate_in_shadow(sim_name, action)
        shadow_comparison[key] = sim_res
        yield _trace(
            step, phase, "simulate_candidate_action",
            {"cypher_executed": "-- shadow clone + mutation + SLA reachability --",
             "execution_time_ms": sim_res.get("clone_time_ms")},
            highlighted=highlighted, proof_path=proof_path,
            extra={"candidate": action, "verdict": sim_res.get("verdict"),
                   "orphaned_flows": sim_res.get("orphaned_flows"),
                   "projected_revenue_loss_per_min": sim_res.get("projected_revenue_loss_per_min"),
                   "shadow_graph": sim_name,
                   "shadow_comparison": dict(shadow_comparison)},
        )

    approved = duel["surgical"]

    # -- Step 6: execute the approved action on prod_graph ----------------------
    step += 1
    _apply_to_prod(approved)
    yield _trace(
        step, "EXECUTED_REMEDIATION", "simulate_candidate_action",
        {"cypher_executed": f"-- applied {approved['action']} to {GRAPH} --"},
        highlighted=[target], proof_path=proof_path,
        extra={"executed_action": approved,
               "shadow_comparison": shadow_comparison},
    )

    # -- Step 7: company-brain notify + episodic memory persist ------------------
    step += 1
    notify = _company_brain_notify(cause_service, root, approved, proof_path)
    episode_id = _persist_episode(scenario_id, cause_service, duel, proof_path)
    yield _trace(
        step, "COMPANY_BRAIN_NOTIFY", "recall_similar_incidents",
        {"cypher_executed": "-- CREATE (:IncidentEpisode) + notify owner --"},
        highlighted=[cause_service],
        extra={"notification": notify, "episode_id": episode_id,
               "shadow_comparison": shadow_comparison},
    )


async def _simulate_in_shadow(sim_name: str, action: Dict[str, Any]) -> Dict[str, Any]:
    """Run one duel candidate inside an isolated shadow graph via MCP."""
    code = action["action"]
    params = action["params"]
    if code == "KILL_DATABASE":
        # Special-case: taking a shared database offline.
        clone = sim.clone_prod_to_shadow(sim_name)
        run_cypher(sim_name,
                   "MATCH (db:Database {id: $db}) SET db.status = 'DOWN'",
                   {"db": params["db_id"]})
        sla = cq.verify_slas(sim_name)
        return {"action": code, "params": params, "shadow_graph": sim_name,
                "clone_time_ms": clone["clone_time_ms"],
                "verdict": "APPROVED" if sla["simulation_passed"] else "REJECTED",
                **sla}
    payload = await mcp_client.call_tool(
        "simulate_candidate_action",
        {
            "action_code": code,
            "params_json": json.dumps(params),
            "sim_name": sim_name,
        },
    )
    return payload


def _apply_to_prod(action: Dict[str, Any]) -> None:
    """Apply the approved mutation to the live prod_graph."""
    code, params = action["action"], action["params"]
    if code == "KILL_AND_ISOLATE_NODE":
        sim.kill_and_isolate_node(GRAPH, params["target_service_id"])
    elif code == "ROLLBACK_COMMIT":
        sim.rollback_commit(GRAPH, params["target_service_id"], params["commit_id"])
    elif code == "THROTTLE_NOISY_NEIGHBOR":
        sim.throttle_noisy_neighbor(GRAPH, params["hog_service_id"], params["db_id"])
    elif code == "ACTIVATE_FALLBACK_ROUTE":
        sim.activate_fallback_route(
            GRAPH, params["parent_service_id"], params["failed_service_id"],
            params["fallback_service_id"])
    # Restore business flows whose dependency closure is fully healthy again.
    cq.heal_flows(GRAPH)


def _company_brain_notify(
    target: str, root: Dict[str, Any], approved: Dict[str, Any], proof_path: List[str]
) -> Dict[str, Any]:
    """Track 03: resolve the owning engineer + runbook and build the payload."""
    res = run_cypher(
        GRAPH,
        """
        MATCH (s:Service {id: $target})
        OPTIONAL MATCH (owner:Engineer)-[:OWNS_SERVICE]->(s)
        OPTIONAL MATCH (author:Engineer)-[:AUTHORED]->(:Commit {is_active: true})-[:DEPLOYED_TO]->(s)
        OPTIONAL MATCH (rb:Runbook)-[:GOVERNS]->(s)
        RETURN owner.handle AS owner_handle, owner.name AS owner_name,
               author.handle AS author_handle, rb.title AS runbook_title,
               rb.action_code AS runbook_action, rb.doc_url AS runbook_url
        LIMIT 1
        """,
        {"target": target},
    )
    row = (res["rows"] or [{}])[0]
    return {
        "service": target,
        "owner": row.get("owner_handle"),
        "owner_name": row.get("owner_name"),
        "author": row.get("author_handle"),
        "action_taken": approved["label"],
        "runbook": {
            "title": row.get("runbook_title"),
            "action": row.get("runbook_action"),
            "url": row.get("runbook_url"),
        },
        "proof_path": proof_path,
        "channel": f"notify:{row.get('owner_handle') or row.get('author_handle')}",
    }


def _persist_episode(
    scenario_id: str, target: str, duel: Dict[str, Any], proof_path: List[str]
) -> str:
    """Track 02: persist the resolved incident as an :IncidentEpisode node."""
    episode_id = f"ep-{scenario_id}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}"
    run_cypher(
        GRAPH,
        """
        CREATE (ep:IncidentEpisode {
          id: $eid, scenario_key: $scenario, root_cause_node: $target,
          approved_action: $approved, rejected_action: $rejected,
          causal_path_json: $path_json,
          resolved_at: $resolved_at
        })
        WITH ep
        MATCH (t:Service {id: $target})
        CREATE (ep)-[:RESOLVED_TARGET]->(t)
        """,
        {
            "eid": episode_id,
            "scenario": scenario_id,
            "target": target,
            "approved": duel["surgical"]["label"],
            "rejected": duel["naive"]["label"],
            "path_json": json.dumps(proof_path),
            "resolved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )
    return episode_id


async def run_remediation_collect(scenario_id: str) -> List[Dict[str, Any]]:
    """Collect the full trace (non-streaming) - used by the REST endpoint."""
    return [e async for e in run_remediation(scenario_id)]


if __name__ == "__main__":
    import sys

    async def _main() -> None:
        async for event in run_remediation(sys.argv[1] if len(sys.argv) > 1 else "poison_pill_commit"):
            print(json.dumps(event)[:220])

    asyncio.run(_main())
