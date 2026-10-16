/** Shared AegisGraph API types. Mirrors the FastAPI contract in backend/main.py. */

export type NodeLabel =
  | "BusinessFlow"
  | "Service"
  | "Database"
  | "Commit"
  | "Engineer"
  | "Runbook"
  | "IncidentEpisode";

export interface GraphNode {
  id: string;
  label: NodeLabel;
  name: string;
  status: string;
  props: Record<string, unknown>;
  // react-force-graph runtime fields
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
  props: Record<string, unknown>;
}

export interface GraphMetrics {
  revenue_at_risk_per_min: number;
  degraded_nodes: number;
  episodic_memories: number;
}

export interface GraphPayload {
  graph_name: string;
  nodes: GraphNode[];
  links: GraphLink[];
  metrics: GraphMetrics;
  available_graphs: string[];
}

export type TracePhase =
  | "MEMORY_LOOKUP"
  | "GRAPH_DIAGNOSIS"
  | "BLAST_RADIUS"
  | "SHADOW_SIM_REJECTED"
  | "SHADOW_SIM_APPROVED"
  | "EXECUTED_REMEDIATION"
  | "COMPANY_BRAIN_NOTIFY"
  | "DONE";

export interface ShadowSimResult {
  action: string;
  params: Record<string, unknown>;
  shadow_graph: string;
  clone_time_ms?: number;
  verdict: "APPROVED" | "REJECTED";
  orphaned_flows?: string[];
  projected_revenue_loss_per_min?: number;
  simulation_passed?: boolean;
}

export interface DuelCandidate {
  action: string;
  params: Record<string, unknown>;
  label: string;
}

export interface TraceEvent {
  step_number: number;
  phase: TracePhase;
  mcp_tool_name: string;
  cypher_executed: string;
  execution_time_ms?: number;
  highlighted_nodes: string[];
  proof_path: string[];
  // phase extras
  episodes_found?: number;
  episodes?: Record<string, unknown>[];
  root_cause?: Record<string, unknown>;
  candidates?: Record<string, unknown>[];
  noisy_neighbor?: Record<string, unknown>[];
  failover_path?: string[];
  impacted_flows?: Record<string, unknown>[];
  revenue_at_risk_per_min?: number;
  candidate?: DuelCandidate;
  verdict?: "APPROVED" | "REJECTED";
  orphaned_flows?: string[];
  projected_revenue_loss_per_min?: number;
  shadow_graph?: string;
  shadow_comparison?: { rejected?: ShadowSimResult; approved?: ShadowSimResult };
  executed_action?: DuelCandidate;
  notification?: {
    service?: string;
    owner?: string;
    owner_name?: string;
    author?: string;
    action_taken?: string;
    runbook?: { title?: string; action?: string; url?: string };
    proof_path?: string[];
    channel?: string;
  };
  episode_id?: string;
  note?: string;
}

export interface Episode {
  episode_id: string;
  scenario_key: string;
  root_cause_node: string;
  approved_action: string;
  rejected_action: string;
  causal_path_json: string;
  resolved_at: string;
  resolved_target: string;
}

export interface ChaosAlert {
  service_id: string;
  name: string;
  status: string;
  error_rate: number;
  latency_ms: number;
  impacted_flows: string[];
}

export interface ScenarioInfo {
  id: string;
  title: string;
  description: string;
  icon: string;
}

export const SCENARIOS: ScenarioInfo[] = [
  {
    id: "poison_pill_commit",
    title: "5-Hop Poison-Pill Commit Cascade",
    description:
      "Activates a buggy regex currency-parser commit on fx-rate-service. Degradation cascades 5 hops upstream — pricing, payments, checkout — putting $7,500/min of revenue at risk.",
    icon: "pill",
  },
  {
    id: "db_pool_exhaustion",
    title: "Shared Redis Connection Pool Starvation",
    description:
      "analytics-batch-worker hogs 960/1000 connections on redis-shared-cluster. Auth, cart and checkout starve while the database saturates.",
    icon: "database",
  },
  {
    id: "gateway_crash_reroute",
    title: "Primary Stripe Connector Outage",
    description:
      "stripe-connector-primary crashes hard. Payment traffic must be rerouted over the shortest healthy path to the adyen-eu-fallback connector.",
    icon: "zap",
  },
];

export const API_BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  (typeof window !== "undefined" ? window.location.origin : "") ||
  "http://localhost:8000";

export function wsUrl(): string {
  return API_BASE.replace(/^http/, "ws") + "/ws/agent";
}
