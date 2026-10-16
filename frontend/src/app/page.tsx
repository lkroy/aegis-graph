"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import AgentTracePanel from "@/components/AgentTracePanel";
import ChaosSidebar from "@/components/ChaosSidebar";
import GraphCanvas from "@/components/GraphCanvas";
import TopNavbar from "@/components/TopNavbar";
import {
  API_BASE,
  wsUrl,
  type ChaosAlert,
  type Episode,
  type GraphLink,
  type GraphMetrics,
  type GraphNode,
  type ShadowSimResult,
  type TraceEvent,
} from "@/types/graph";

const base = API_BASE.replace(/\/$/, "");

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

const EMPTY_METRICS: GraphMetrics = {
  revenue_at_risk_per_min: 0,
  degraded_nodes: 0,
  episodic_memories: 0,
};

export default function Home() {
  const [graphName, setGraphName] = useState("prod_graph");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [availableGraphs, setAvailableGraphs] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<GraphMetrics>(EMPTY_METRICS);

  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<ChaosAlert[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);

  const [highlight, setHighlight] = useState<Set<string>>(new Set());
  const [proofPath, setProofPath] = useState<string[]>([]);
  const [shadowComparison, setShadowComparison] = useState<{
    rejected?: ShadowSimResult;
    approved?: ShadowSimResult;
  }>({});
  const [ownership, setOwnership] = useState<TraceEvent["notification"] | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef(false);

  const showError = useCallback((msg: string) => {
    setError(msg);
    window.setTimeout(() => setError(null), 7000);
  }, []);

  const loadGraph = useCallback(
    async (name: string) => {
      try {
        const data = await api<{
          nodes: GraphNode[];
          links: GraphLink[];
          metrics: GraphMetrics;
          available_graphs: string[];
        }>(`/api/graph?graph_name=${encodeURIComponent(name)}`);
        setNodes(data.nodes ?? []);
        setLinks(data.links ?? []);
        setMetrics(data.metrics ?? EMPTY_METRICS);
        setAvailableGraphs(data.available_graphs ?? []);
        setGraphName(name);
      } catch (e) {
        showError(e instanceof Error ? e.message : "Failed to load graph");
      }
    },
    [showError]
  );

  const fetchEpisodes = useCallback(async () => {
    try {
      const data = await api<{ episodes: Episode[] }>("/api/episodes");
      setEpisodes(data.episodes ?? []);
    } catch {
      /* non-fatal */
    }
  }, []);

  useEffect(() => {
    void loadGraph("prod_graph");
    void fetchEpisodes();
  }, [loadGraph, fetchEpisodes]);

  const clearRunState = () => {
    setTrace([]);
    setHighlight(new Set());
    setProofPath([]);
    setShadowComparison({});
    setOwnership(null);
  };

  const injectChaos = async (scenarioId: string) => {
    setLoading(true);
    clearRunState();
    try {
      const data = await api<{
        alerts: ChaosAlert[];
        metrics: GraphMetrics;
        nodes: GraphNode[];
        links: GraphLink[];
      }>(`/api/chaos/${scenarioId}`, { method: "POST" });
      setNodes(data.nodes ?? []);
      setLinks(data.links ?? []);
      setMetrics(data.metrics ?? EMPTY_METRICS);
      setAlerts(data.alerts ?? []);
      setActiveScenario(scenarioId);
      setGraphName("prod_graph");
      await fetchEpisodes();
    } catch (e) {
      showError(e instanceof Error ? e.message : "Chaos injection failed");
    } finally {
      setLoading(false);
    }
  };

  const resetAll = async () => {
    setLoading(true);
    try {
      await api("/api/reset", { method: "POST" });
      clearRunState();
      setAlerts([]);
      setActiveScenario(null);
      await loadGraph("prod_graph");
      await fetchEpisodes();
    } catch (e) {
      showError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  /** Apply one streamed trace event to the UI. */
  const applyEvent = useCallback((ev: TraceEvent) => {
    setTrace((t) => [...t, ev]);
    setHighlight(new Set(ev.highlighted_nodes ?? []));
    setProofPath(ev.proof_path ?? []);
    if (ev.shadow_comparison) {
      setShadowComparison((prev) => ({ ...prev, ...ev.shadow_comparison }));
    }
    if (ev.phase === "COMPANY_BRAIN_NOTIFY" && ev.notification) {
      setOwnership(ev.notification);
    }
  }, []);

  const finishRun = useCallback(
    (finalNodes: GraphNode[], finalLinks: GraphLink[], finalMetrics: GraphMetrics) => {
      setNodes(finalNodes);
      setLinks(finalLinks);
      setMetrics(finalMetrics);
      setGraphName("prod_graph");
      setRunning(false);
      void fetchEpisodes();
    },
    [fetchEpisodes]
  );

  /** REST fallback: play the collected trace back with timed steps. */
  const runAgentRest = useCallback(
    async (scenarioId: string) => {
      const data = await api<{
        trace: TraceEvent[];
        metrics: GraphMetrics;
        nodes: GraphNode[];
        links: GraphLink[];
      }>("/api/agent/remediate", {
        method: "POST",
        body: JSON.stringify({ scenario_id: scenarioId }),
      });
      for (const ev of data.trace ?? []) {
        if (cancelled.current) break;
        applyEvent(ev);
        await new Promise((r) => setTimeout(r, 900));
      }
      if (!cancelled.current) {
        finishRun(data.nodes ?? [], data.links ?? [], data.metrics ?? EMPTY_METRICS);
      }
    },
    [applyEvent, finishRun]
  );

  const runAgent = useCallback(() => {
    if (!activeScenario || running || loading) return;
    const scenarioId = activeScenario;
    cancelled.current = false;
    clearRunState();
    setRunning(true);

    let settled = false;
    const done = () => {
      settled = true;
    };

    // Primary path: live WebSocket streaming.
    try {
      const ws = new WebSocket(wsUrl());
      const guard = window.setTimeout(() => {
        if (!settled) {
          try {
            ws.close();
          } catch {
            /* noop */
          }
          // Fall back to REST if the socket never produced an event.
          void runAgentRest(scenarioId)
            .catch((e) => {
              showError(e instanceof Error ? e.message : "Agent run failed");
              setRunning(false);
            })
            .finally(done);
        }
      }, 9000);

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: "remediate", scenario_id: scenarioId }));
      };
      ws.onmessage = (msg) => {
        try {
          const ev = JSON.parse(msg.data as string) as TraceEvent & {
            nodes?: GraphNode[];
            links?: GraphLink[];
            metrics?: GraphMetrics;
          };
          if (ev.phase === "DONE") {
            window.clearTimeout(guard);
            try {
              ws.close();
            } catch {
              /* noop */
            }
            finishRun(ev.nodes ?? [], ev.links ?? [], ev.metrics ?? EMPTY_METRICS);
            done();
          } else if (ev.step_number !== undefined) {
            window.clearTimeout(guard);
            applyEvent(ev);
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onerror = () => {
        if (!settled) {
          window.clearTimeout(guard);
          try {
            ws.close();
          } catch {
            /* noop */
          }
          void runAgentRest(scenarioId)
            .catch((e) => {
              showError(e instanceof Error ? e.message : "Agent run failed");
              setRunning(false);
            })
            .finally(done);
        }
      };
    } catch {
      void runAgentRest(scenarioId)
        .catch((e) => {
          showError(e instanceof Error ? e.message : "Agent run failed");
          setRunning(false);
        })
        .finally(done);
    }
  }, [activeScenario, running, loading, applyEvent, finishRun, runAgentRest, showError]);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const onHighlightStep = useCallback((ev: TraceEvent) => {
    setHighlight(new Set(ev.highlighted_nodes ?? []));
    setProofPath(ev.proof_path ?? []);
    setGraphName("prod_graph");
  }, []);

  const currentPhase = trace.length > 0 ? trace[trace.length - 1].phase : null;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <TopNavbar
        graphName={graphName}
        availableGraphs={availableGraphs}
        onSwitchGraph={(g) => void loadGraph(g)}
        metrics={metrics}
      />

      {error && (
        <div className="shrink-0 border-b border-rose-900 bg-rose-950/60 px-4 py-1.5 text-xs text-rose-300">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <ChaosSidebar
          activeScenario={activeScenario}
          running={running}
          busy={running || loading}
          alerts={alerts}
          episodes={episodes}
          trace={trace}
          onInject={(id) => void injectChaos(id)}
          onRunAgent={runAgent}
          onReset={() => void resetAll()}
        />

        <main className="relative min-w-0 flex-1 bg-slate-950">
          <GraphCanvas
            nodes={nodes}
            links={links}
            highlighted={highlight}
            proofPath={proofPath}
          />
          {running && currentPhase && (
            <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full border border-cyan-800 bg-slate-900/90 px-4 py-1.5 font-mono text-[11px] text-cyan-300 shadow-lg">
              <span className="mr-2 inline-block h-2 w-2 animate-ping rounded-full bg-cyan-400" />
              AGENT · {currentPhase} · step {trace.length}
            </div>
          )}
        </main>

        <AgentTracePanel
          trace={trace}
          shadowComparison={shadowComparison}
          ownership={ownership}
          onHighlightStep={onHighlightStep}
        />
      </div>
    </div>
  );
}
