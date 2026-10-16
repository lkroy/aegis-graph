"""Seeds prod_graph with a deterministic 43-node / 66-edge enterprise topology.

Run:  python -m graph.seed_topology   (from backend/)
Idempotent: wipes prod_graph first, then rebuilds it in batched UNWIND writes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from config import settings
from graph.client import delete_graph, graph, run_cypher

# ----------------------------------------------------------------------------
# Node definitions
# ----------------------------------------------------------------------------

BUSINESS_FLOWS: List[Dict[str, Any]] = [
    {"id": "bf-global-checkout", "name": "Global Web Checkout", "revenue_per_min": 4500, "status": "HEALTHY"},
    {"id": "bf-eu-checkout", "name": "EU Mobile Checkout", "revenue_per_min": 1800, "status": "HEALTHY"},
    {"id": "bf-b2b-invoicing", "name": "Enterprise Subscription Renewal", "revenue_per_min": 1200, "status": "HEALTHY"},
]

# (id, name, tier, latency_ms)
SERVICES = [
    # Tier 1 - ingress
    ("api-gateway", "API Gateway", 1, 45),
    ("eu-edge-router", "EU Edge Router", 1, 60),
    ("b2b-portal-ui", "B2B Portal UI", 1, 90),
    # Tier 2 - core domain
    ("checkout-service", "Checkout Service", 2, 120),
    ("order-orchestrator", "Order Orchestrator", 2, 140),
    ("cart-service", "Cart Service", 2, 110),
    ("subscription-mgr", "Subscription Manager", 2, 130),
    ("auth-session-svc", "Auth Session Service", 2, 95),
    # Tier 3 - payment & pricing
    ("payment-router", "Payment Router", 3, 180),
    ("stripe-connector-primary", "Stripe Connector (Primary)", 3, 210),
    ("adyen-eu-fallback", "Adyen EU Fallback", 3, 230),
    ("pricing-engine", "Pricing Engine", 3, 170),
    ("tax-calculator", "Tax Calculator", 3, 150),
    ("fraud-scoring-svc", "Fraud Scoring Service", 3, 190),
    # Tier 4 - foundational & async
    ("fx-rate-service", "FX Rate Service", 4, 90),
    ("inventory-ledger", "Inventory Ledger", 4, 100),
    ("notification-worker", "Notification Worker", 4, 80),
    ("analytics-batch-worker", "Analytics Batch Worker", 4, 300),
    ("token-vault-svc", "Token Vault Service", 4, 85),
]

DATABASES = [
    ("redis-shared-cluster", "Redis Shared Cluster", "redis", 1000),
    ("orders-postgres-primary", "Orders Postgres Primary", "postgres", 500),
    ("fx-rates-timeseries-db", "FX Rates Timeseries DB", "timescaledb", 200),
    ("vault-encrypted-store", "Vault Encrypted Store", "vault", 150),
    ("inventory-cockroachdb", "Inventory CockroachDB", "cockroachdb", 400),
]

COMMITS = [
    # id, hash, message, timestamp, is_active, is_buggy, service, author
    ("commit-9f82a", "#9f82a", "feat: regex currency parser", "2026-10-15T08:12:00Z", False, True, "fx-rate-service", "sarah_chen"),
    ("commit-7b31c", "#7b31c", "fix: rounding edge cases", "2026-10-14T16:40:00Z", True, False, "fx-rate-service", "sarah_chen"),
    ("commit-41de0", "#41de0", "perf: connection reuse", "2026-10-13T11:02:00Z", True, False, "analytics-batch-worker", "marcus_data"),
    ("commit-88aa1", "#88aa1", "feat: 3ds2 fallback", "2026-10-12T09:25:00Z", True, False, "payment-router", "lena_sre"),
    ("commit-02cf9", "#02cf9", "chore: bump stripe sdk", "2026-10-11T14:55:00Z", True, False, "stripe-connector-primary", "raj_backend"),
    ("commit-5e77d", "#5e77d", "feat: session ttl", "2026-10-10T10:18:00Z", True, False, "auth-session-svc", "yuki_infra"),
]

ENGINEERS = [
    ("sarah_chen", "@sarah_chen", "Sarah Chen", "Payments", "Senior Backend Engineer"),
    ("marcus_data", "@marcus_data", "Marcus Webb", "Data Platform", "Data Engineer"),
    ("lena_sre", "@lena_sre", "Lena Kowalski", "SRE", "Site Reliability Engineer"),
    ("raj_backend", "@raj_backend", "Raj Patel", "Checkout", "Backend Engineer"),
    ("yuki_infra", "@yuki_infra", "Yuki Tanaka", "Infrastructure", "Platform Engineer"),
    ("ana_mobile", "@ana_mobile", "Ana Silva", "Mobile", "Mobile Engineer"),
]

RUNBOOKS = [
    ("rb-rollback-deploy", "Rollback faulty deploy", "ROLLBACK_COMMIT", "https://runbooks.internal/rb-rollback-deploy"),
    ("rb-throttle-redis", "Throttle noisy Redis neighbor", "THROTTLE_NOISY_NEIGHBOR", "https://runbooks.internal/rb-throttle-redis"),
    ("rb-failover-payments", "Activate payment fallback route", "ACTIVATE_FALLBACK_ROUTE", "https://runbooks.internal/rb-failover-payments"),
    ("rb-isolate-node", "Circuit-break failing node", "KILL_AND_ISOLATE_NODE", "https://runbooks.internal/rb-isolate-node"),
]

# ----------------------------------------------------------------------------
# Edge definitions  (source_id, target_id, rel_type, props)
# ----------------------------------------------------------------------------

CALLS = [
    # tier 1 -> tier 2
    ("api-gateway", "checkout-service", "PRIMARY"),
    ("api-gateway", "cart-service", "PRIMARY"),
    ("api-gateway", "auth-session-svc", "PRIMARY"),
    ("eu-edge-router", "checkout-service", "PRIMARY"),
    ("eu-edge-router", "cart-service", "PRIMARY"),
    ("b2b-portal-ui", "subscription-mgr", "PRIMARY"),
    ("b2b-portal-ui", "auth-session-svc", "PRIMARY"),
    # tier 2 -> tier 3 / tier 4
    ("checkout-service", "order-orchestrator", "PRIMARY"),
    ("checkout-service", "pricing-engine", "PRIMARY"),
    ("checkout-service", "fraud-scoring-svc", "PRIMARY"),
    ("order-orchestrator", "payment-router", "PRIMARY"),
    ("order-orchestrator", "inventory-ledger", "PRIMARY"),
    ("order-orchestrator", "notification-worker", "PRIMARY"),
    ("cart-service", "pricing-engine", "PRIMARY"),
    ("cart-service", "inventory-ledger", "PRIMARY"),
    ("subscription-mgr", "payment-router", "PRIMARY"),
    ("subscription-mgr", "tax-calculator", "PRIMARY"),
    ("auth-session-svc", "token-vault-svc", "PRIMARY"),
    # tier 3 internal
    ("payment-router", "stripe-connector-primary", "PRIMARY"),
    ("payment-router", "adyen-eu-fallback", "FALLBACK"),
    ("payment-router", "pricing-engine", "PRIMARY"),
    ("pricing-engine", "fx-rate-service", "PRIMARY"),
    ("pricing-engine", "tax-calculator", "PRIMARY"),
]

READS_WRITES = [
    # (service, db, conn_weight)
    ("fx-rate-service", "fx-rates-timeseries-db", 40),
    ("inventory-ledger", "inventory-cockroachdb", 60),
    ("analytics-batch-worker", "redis-shared-cluster", 120),
    ("token-vault-svc", "vault-encrypted-store", 30),
    ("auth-session-svc", "redis-shared-cluster", 220),
    ("cart-service", "redis-shared-cluster", 180),
    ("checkout-service", "redis-shared-cluster", 260),
    ("checkout-service", "orders-postgres-primary", 140),
    ("order-orchestrator", "orders-postgres-primary", 160),
    ("subscription-mgr", "orders-postgres-primary", 90),
    ("fraud-scoring-svc", "redis-shared-cluster", 80),
    ("pricing-engine", "redis-shared-cluster", 110),
]

DEPENDS_ON = [
    ("bf-global-checkout", "api-gateway"),
    ("bf-eu-checkout", "eu-edge-router"),
    ("bf-b2b-invoicing", "b2b-portal-ui"),
]

OWNS_SERVICE = [
    ("sarah_chen", "fx-rate-service"),
    ("sarah_chen", "pricing-engine"),
    ("marcus_data", "analytics-batch-worker"),
    ("lena_sre", "payment-router"),
    ("lena_sre", "api-gateway"),
    ("raj_backend", "checkout-service"),
    ("raj_backend", "cart-service"),
    ("raj_backend", "stripe-connector-primary"),
    ("yuki_infra", "auth-session-svc"),
    ("yuki_infra", "token-vault-svc"),
    ("ana_mobile", "eu-edge-router"),
    ("ana_mobile", "b2b-portal-ui"),
]

GOVERNS = [
    ("rb-rollback-deploy", "fx-rate-service"),
    ("rb-throttle-redis", "analytics-batch-worker"),
    ("rb-failover-payments", "payment-router"),
    ("rb-isolate-node", "stripe-connector-primary"),
]


def seed() -> Dict[str, int]:
    """Wipe and rebuild prod_graph. Returns node/edge counts.

    Uses one trivially-correct UNWIND per label / relationship type:
    CREATE (n:<Label>) SET n = row.
    """
    delete_graph(settings.prod_graph)
    g = graph(settings.prod_graph)

    by_label: Dict[str, List[Dict[str, Any]]] = {}
    for bf in BUSINESS_FLOWS:
        by_label.setdefault("BusinessFlow", []).append(dict(bf))
    for sid, name, tier, latency in SERVICES:
        by_label.setdefault("Service", []).append({
            "id": sid, "name": name, "tier": tier,
            "status": "HEALTHY", "error_rate": 0.01, "latency_ms": latency,
        })
    for did, name, engine, max_conns in DATABASES:
        by_label.setdefault("Database", []).append({
            "id": did, "name": name, "engine": engine,
            "active_conns": max_conns // 4, "max_conns": max_conns,
            "status": "HEALTHY",
        })
    for cid, chash, msg, ts, active, buggy, _svc, _author in COMMITS:
        by_label.setdefault("Commit", []).append({
            "id": cid, "hash": chash, "message": msg,
            "timestamp": ts, "is_active": active, "is_buggy": buggy,
        })
    for eid, handle, name, team, role in ENGINEERS:
        by_label.setdefault("Engineer", []).append({
            "id": eid, "handle": handle, "name": name,
            "team": team, "role": role,
        })
    for rid, title, action_code, doc_url in RUNBOOKS:
        by_label.setdefault("Runbook", []).append({
            "id": rid, "title": title, "action_code": action_code,
            "doc_url": doc_url,
        })

    for label, rows in by_label.items():
        g.query(f"UNWIND $rows AS row CREATE (n:{label}) SET n = row",
                {"rows": rows})

    by_rel: Dict[str, List[Dict[str, Any]]] = {}
    for src, dst, route_type in CALLS:
        by_rel.setdefault("CALLS", []).append(
            {"src": src, "dst": dst,
             "props": {"weight": 1.0, "route_type": route_type}})
    for src, dst, w in READS_WRITES:
        by_rel.setdefault("READS_WRITES", []).append(
            {"src": src, "dst": dst, "props": {"conn_weight": w}})
    for src, dst in DEPENDS_ON:
        by_rel.setdefault("DEPENDS_ON", []).append(
            {"src": src, "dst": dst, "props": {"critical": True}})
    for cid, _, _, _, _, _, svc, _ in COMMITS:
        by_rel.setdefault("DEPLOYED_TO", []).append(
            {"src": cid, "dst": svc, "props": {}})
    for cid, _, _, _, _, _, _, author in COMMITS:
        by_rel.setdefault("AUTHORED", []).append(
            {"src": author, "dst": cid, "props": {}})
    for eng, svc in OWNS_SERVICE:
        by_rel.setdefault("OWNS_SERVICE", []).append(
            {"src": eng, "dst": svc, "props": {}})
    for rb, svc in GOVERNS:
        by_rel.setdefault("GOVERNS", []).append(
            {"src": rb, "dst": svc, "props": {}})

    for rel, rows in by_rel.items():
        g.query(
            f"""
            UNWIND $rows AS e
            MATCH (a {{id: e.src}}), (b {{id: e.dst}})
            CREATE (a)-[r:{rel}]->(b)
            SET r = e.props
            """,
            {"rows": rows},
        )

    counts = run_cypher(
        settings.prod_graph,
        "MATCH (n) WITH count(n) AS nodes MATCH ()-[r]->() "
        "RETURN nodes, count(r) AS edges",
    )["rows"][0]
    return {"nodes": counts["nodes"], "edges": counts["edges"]}


if __name__ == "__main__":
    result = seed()
    print(f"Seeded prod_graph: {result['nodes']} nodes, {result['edges']} edges")
