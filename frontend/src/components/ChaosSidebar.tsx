"use client";

import {
  AlertTriangle,
  Archive,
  Database,
  History,
  Loader2,
  RotateCcw,
  Sparkles,
  Zap,
} from "lucide-react";
import type { ChaosAlert, Episode, TraceEvent } from "@/types/graph";
import { SCENARIOS } from "@/types/graph";
import { cn } from "@/lib/cn";

interface Props {
  activeScenario: string | null;
  running: boolean;
  busy: boolean;
  alerts: ChaosAlert[];
  episodes: Episode[];
  trace: TraceEvent[];
  onInject: (scenarioId: string) => void;
  onRunAgent: () => void;
  onReset: () => void;
}

const ICONS: Record<string, typeof Zap> = {
  pill: Sparkles,
  database: Database,
  zap: Zap,
};

function scenarioTitle(id: string): string {
  return SCENARIOS.find((s) => s.id === id)?.title ?? id;
}

export default function ChaosSidebar({
  activeScenario,
  running,
  busy,
  alerts,
  episodes,
  trace,
  onInject,
  onRunAgent,
  onReset,
}: Props) {
  const lastEpisode = episodes[0];
  const memoryPhase = trace.find((t) => t.phase === "MEMORY_LOOKUP");

  return (
    <aside className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r border-slate-800 bg-slate-950/60 p-3 slim-scroll">
      <section>
        <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
          Chaos Injection
        </h2>
        <div className="flex flex-col gap-2">
          {SCENARIOS.map((s) => {
            const Icon = ICONS[s.icon] ?? Zap;
            const active = activeScenario === s.id;
            return (
              <button
                key={s.id}
                disabled={busy}
                onClick={() => onInject(s.id)}
                className={cn(
                  "rounded-lg border p-2.5 text-left transition-all",
                  active
                    ? "border-rose-500/60 bg-rose-500/10"
                    : "border-slate-800 bg-slate-900/60 hover:border-slate-600 hover:bg-slate-900",
                  busy && "cursor-not-allowed opacity-60"
                )}
              >
                <div className="flex items-center gap-2">
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active ? "text-rose-400" : "text-slate-400"
                    )}
                  />
                  <span className="text-[13px] font-semibold leading-tight text-slate-100">
                    {s.title}
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-snug text-slate-400">
                  {s.description}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <button
          onClick={onRunAgent}
          disabled={busy || !activeScenario}
          title={!activeScenario ? "Inject a chaos scenario first" : "Run the autonomous remediation agent"}
          className={cn(
            "animate-glow flex items-center justify-center gap-2 rounded-lg bg-cyan-500 px-3 py-3 text-sm font-bold text-slate-950 transition-all",
            busy || !activeScenario
              ? "cursor-not-allowed opacity-40"
              : "hover:bg-cyan-400"
          )}
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Zap className="h-4 w-4" />
          )}
          {running ? "Agent Remediating…" : "⚡ Run Autonomous FalkorDB Agent"}
        </button>
        <button
          onClick={onReset}
          disabled={busy}
          className={cn(
            "flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100",
            busy && "cursor-not-allowed opacity-60"
          )}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset Production Topology
        </button>
      </section>

      {alerts.length > 0 && (
        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Active Alerts
          </h2>
          <div className="flex flex-col gap-1.5">
            {alerts.slice(0, 8).map((a) => (
              <div
                key={a.service_id}
                className="rounded-md border border-rose-900/60 bg-rose-950/40 px-2 py-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-semibold text-rose-300">
                    {a.service_id}
                  </span>
                  <span className="rounded bg-rose-500/20 px-1.5 py-0.5 text-[10px] font-bold text-rose-300">
                    {a.status}
                  </span>
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-slate-400">
                  err {Math.round((a.error_rate ?? 0) * 100)}% ·{" "}
                  {a.latency_ms ?? 0}ms · flows:{" "}
                  {(a.impacted_flows ?? []).join(", ") || "—"}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-auto">
        <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          <History className="h-3.5 w-3.5 text-violet-400" />
          Episodic Memory Vault
        </h2>
        {episodes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-3 text-center text-[11px] text-slate-500">
            <Archive className="mx-auto mb-1 h-4 w-4" />
            No incident episodes stored yet.
            <br />
            Resolved incidents persist here across runs.
          </div>
        ) : (
          <div className="flex max-h-64 flex-col gap-1.5 overflow-y-auto slim-scroll">
            {episodes.map((ep) => (
              <div
                key={ep.episode_id}
                className="rounded-md border border-violet-900/50 bg-violet-950/30 px-2 py-1.5"
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="truncate font-mono text-[11px] font-semibold text-violet-300">
                    {ep.root_cause_node}
                  </span>
                  <span className="shrink-0 text-[10px] text-slate-500">
                    {ep.resolved_at ? ep.resolved_at.slice(0, 10) : ""}
                  </span>
                </div>
                <div className="mt-0.5 text-[10px] text-slate-400">
                  {scenarioTitle(ep.scenario_key)}
                </div>
                <div className="mt-0.5 truncate text-[10px] text-slate-500">
                  ✓ {ep.approved_action}
                </div>
              </div>
            ))}
          </div>
        )}
        {memoryPhase && memoryPhase.episodes_found !== undefined && (
          <div className="mt-2 rounded-md border border-slate-800 bg-slate-900/60 px-2 py-1.5 text-[10px] text-slate-400">
            Last memory lookup:{" "}
            <span className="font-semibold text-violet-300">
              {memoryPhase.episodes_found}
            </span>{" "}
            similar episode(s) found
            {lastEpisode ? ` — newest: ${lastEpisode.episode_id}` : ""}
          </div>
        )}
      </section>
    </aside>
  );
}
