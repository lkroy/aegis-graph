"use client";

import { Activity, BrainCircuit, Database, ShieldCheck } from "lucide-react";
import type { GraphMetrics } from "@/types/graph";
import { cn } from "@/lib/cn";

interface Props {
  graphName: string;
  availableGraphs: string[];
  onSwitchGraph: (name: string) => void;
  metrics: GraphMetrics;
}

const GRAPH_LABELS: Record<string, { label: string; hint: string }> = {
  prod_graph: { label: "prod_graph", hint: "Live Production" },
  sim_rejected: { label: "sim_rejected", hint: "Shadow Sim #1 — Blocked" },
  sim_approved: { label: "sim_approved", hint: "Shadow Sim #2 — Verified" },
};

function fmtMoney(n: number): string {
  return "$" + n.toLocaleString("en-US");
}

export default function TopNavbar({
  graphName,
  availableGraphs,
  onSwitchGraph,
  metrics,
}: Props) {
  const atRisk = metrics.revenue_at_risk_per_min > 0;
  // Always show the three canonical tenants; merge any extra graphs the API reports.
  const pills = ["prod_graph", "sim_rejected", "sim_approved"];
  for (const g of availableGraphs) {
    if (!pills.includes(g)) pills.push(g);
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-slate-800 bg-slate-950/90 px-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-6 w-6 text-cyan-400" />
        <span className="text-lg font-bold tracking-tight text-slate-100">
          AegisGraph
        </span>
        <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-cyan-300">
          FalkorDB Multigraph + MCP Engine
        </span>
      </div>

      <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 p-1">
        <Database className="ml-1 h-3.5 w-3.5 text-slate-500" />
        {pills.map((g) => {
          const meta = GRAPH_LABELS[g] ?? { label: g, hint: "Shadow graph" };
          const active = graphName === g;
          return (
            <button
              key={g}
              title={meta.hint}
              onClick={() => onSwitchGraph(g)}
              className={cn(
                "rounded-md px-2.5 py-1 font-mono text-[11px] transition-colors",
                active
                  ? g === "prod_graph"
                    ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/50"
                    : g === "sim_rejected"
                      ? "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/50"
                      : "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/50"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              )}
            >
              {meta.label}
            </button>
          );
        })}
      </div>

      <div className="ml-auto flex items-center gap-5">
        <div className="flex items-center gap-2">
          <Activity
            className={cn(
              "h-4 w-4",
              atRisk ? "animate-pulse-red text-rose-500" : "text-emerald-400"
            )}
          />
          <div className="leading-tight">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              Revenue at Risk
            </div>
            <div
              className={cn(
                "font-mono text-sm font-bold",
                atRisk ? "animate-pulse-red text-rose-400" : "text-emerald-400"
              )}
            >
              {fmtMoney(metrics.revenue_at_risk_per_min)}/min
            </div>
          </div>
        </div>
        <div className="leading-tight">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Degraded Nodes
          </div>
          <div
            className={cn(
              "font-mono text-sm font-bold",
              metrics.degraded_nodes > 0 ? "text-amber-400" : "text-emerald-400"
            )}
          >
            {metrics.degraded_nodes}
          </div>
        </div>
        <div className="flex items-center gap-2 leading-tight">
          <BrainCircuit className="h-4 w-4 text-violet-400" />
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              Episodic Memories
            </div>
            <div className="font-mono text-sm font-bold text-violet-300">
              {metrics.episodic_memories}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
