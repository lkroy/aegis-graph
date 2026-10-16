"""Deterministic chaos injectors. Each scenario mutates prod_graph with Cypher and
propagates degraded state across multi-hop cascades.

Run: python -m graph.chaos_engine <scenario_id>   (from backend/)
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from config import settings
from graph.client import run_cypher

GRAPH = settings.prod_graph

# Upstream cascade order for scenario 1 (each CALLS the next, upstream first).
SCENARIO_1_CASCADE = [
    "fx-rate-service",      # hop 0: fault origin
    "pricing-engine",       # hop 1
    "payment-router",       # hop 2
    "order-orchestrator",   # hop 3
    "checkout-service",     # hop 4
    "api-gateway",          # hop 5
    "eu-edge-router",       # hop 5 (parallel ingress)
]

SCENARIO_1_FLOWS = ["bf-global-checkout", "bf-eu-checkout"]


def inject_poison_pill_commit() -> Dict[str, Any]:
    """Scenario 1: activate the buggy regex-parser commit on fx-rate-service and
    cascade DEGRADED state 5 hops upstream."""
    # 1. Flip the poison-pill commit to active.
    run_cypher(
        GRAPH,
        """
        MATCH (c:Commit {id: 'commit-9f82a'})-[:DEPLOYED_TO]->(s:Service {id: 'fx-rate-service'})
        SET c.is_active = true
        SET s.status = 'DEGRADED', s.error_rate = 0.68, s.latency_ms = 4200
        RETURN c.hash AS hash
        """,
    )
    # 2. Deactivate the previously healthy commit on the same service.
    run_cypher(
        GRAPH,
        """
        MATCH (c:Commit {id: 'commit-7b31c'})
        SET c.is_active = false
        """,
    )
    # 3. Propagate degradation upstream hop by hop.
    for svc in SCENARIO_1_CASCADE[1:]:
        run_cypher(
            GRAPH,
            """
            MATCH (s:Service {id: $svc})
            SET s.status = 'DEGRADED', s.error_rate = 0.68, s.latency_ms = 4200
            """,
            {"svc": svc},
        )
    # 4. Mark impacted business flows AT_RISK (all three: the payment-router
    #    degradation also breaks b2b invoicing via subscription-mgr).
    for flow in ["bf-global-checkout", "bf-eu-checkout", "bf-b2b-invoicing"]:
        run_cypher(
            GRAPH,
            "MATCH (bf:BusinessFlow {id: $flow}) SET bf.status = 'AT_RISK'",
            {"flow": flow},
        )
    return {
        "scenario": "poison_pill_commit",
        "title": "5-Hop Poison-Pill Commit Cascade",
        "origin": "fx-rate-service",
        "commit": "#9f82a",
        "degraded_services": SCENARIO_1_CASCADE,
        "flows_at_risk": ["bf-global-checkout", "bf-eu-checkout", "bf-b2b-invoicing"],
        "revenue_at_risk_per_min": 7500,
    }


def inject_db_pool_exhaustion() -> Dict[str, Any]:
    """Scenario 2: analytics-batch-worker hogs the shared Redis pool."""
    run_cypher(
        GRAPH,
        """
        MATCH (hog:Service {id: 'analytics-batch-worker'})-[r:READS_WRITES]->
              (db:Database {id: 'redis-shared-cluster'})
        SET r.conn_weight = 960,
            db.status = 'SATURATED',
            db.active_conns = 960
        """,
    )
    starved = ["auth-session-svc", "cart-service", "checkout-service"]
    for svc in starved:
        run_cypher(
            GRAPH,
            """
            MATCH (s:Service {id: $svc})
            SET s.status = 'DEGRADED', s.error_rate = 0.52, s.latency_ms = 3800
            """,
            {"svc": svc},
        )
    for flow in ["bf-global-checkout", "bf-eu-checkout", "bf-b2b-invoicing"]:
        run_cypher(
            GRAPH,
            "MATCH (bf:BusinessFlow {id: $flow}) SET bf.status = 'AT_RISK'",
            {"flow": flow},
        )
    return {
        "scenario": "db_pool_exhaustion",
        "title": "Shared Redis Connection Pool Starvation",
        "origin": "analytics-batch-worker",
        "bottleneck_db": "redis-shared-cluster",
        "degraded_services": starved,
        "flows_at_risk": ["bf-global-checkout", "bf-eu-checkout", "bf-b2b-invoicing"],
        "revenue_at_risk_per_min": 7500,
    }


def inject_gateway_crash() -> Dict[str, Any]:
    """Scenario 3: primary Stripe connector crashes; traffic must fail over."""
    run_cypher(
        GRAPH,
        """
        MATCH (s:Service {id: 'stripe-connector-primary'})
        SET s.status = 'DOWN', s.error_rate = 1.0, s.latency_ms = 0
        """,
    )
    for svc in ["payment-router", "order-orchestrator", "checkout-service"]:
        run_cypher(
            GRAPH,
            """
            MATCH (s:Service {id: $svc})
            SET s.status = 'DEGRADED', s.error_rate = 0.61, s.latency_ms = 3900
            """,
            {"svc": svc},
        )
    for flow in ["bf-global-checkout", "bf-eu-checkout", "bf-b2b-invoicing"]:
        run_cypher(
            GRAPH,
            "MATCH (bf:BusinessFlow {id: $flow}) SET bf.status = 'AT_RISK'",
            {"flow": flow},
        )
    return {
        "scenario": "gateway_crash_reroute",
        "title": "Primary Stripe Connector Outage",
        "origin": "stripe-connector-primary",
        "degraded_services": ["payment-router", "order-orchestrator", "checkout-service"],
        "flows_at_risk": ["bf-global-checkout", "bf-eu-checkout", "bf-b2b-invoicing"],
        "revenue_at_risk_per_min": 7500,
    }


SCENARIOS = {
    "poison_pill_commit": inject_poison_pill_commit,
    "db_pool_exhaustion": inject_db_pool_exhaustion,
    "gateway_crash_reroute": inject_gateway_crash,
}


def inject(scenario_id: str) -> Dict[str, Any]:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_id}. Choose from {list(SCENARIOS)}")
    return SCENARIOS[scenario_id]()


def active_alerts() -> List[Dict[str, Any]]:
    """Current degraded/down services and at-risk flows in prod_graph."""
    res = run_cypher(
        GRAPH,
        """
        MATCH (s:Service)
        WHERE s.status IN ['DEGRADED', 'DOWN']
        OPTIONAL MATCH (bf:BusinessFlow)-[:DEPENDS_ON]->(:Service)-[:CALLS*0..6]->(s)
        WITH s, collect(DISTINCT bf.id) AS impacted_flows
        RETURN s.id AS service_id, s.name AS name, s.status AS status,
               s.error_rate AS error_rate, s.latency_ms AS latency_ms,
               impacted_flows
        ORDER BY s.tier DESC
        """,
    )
    return res["rows"]


if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "poison_pill_commit"
    print(inject(scenario))
