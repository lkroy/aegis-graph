"use client";

import { useState } from "react";
import {
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Cpu,
  GitBranch,
  Route,
  ShieldAlert,
  User,
  XCircle,
} from "lucide-react";
import type { ShadowSimResult, TraceEvent } from "@/types/graph";
import { cn } from "@/lib/cn";

interface Props {
  trace: TraceEvent[];
  shadowComparison: { rejected?: ShadowSimResult; approved?: ShadowSimResult };
  ownership: TraceEvent["notification"] | null;
  onHighlightStep: (ev: TraceEvent) => void;
}

const PHASE_META: Record<string, { label: string; icon: typeof Cpu; color: string }> = {
  MEMORY_LOOKUP: { label: "Episodic Memory Lookup", icon: BrainCircuit, color: "text-violet-400" },
  GRAPH_DIAGNOSIS: { label: "Graph Diagnosis", icon: Cpu, color: "text-cyan-400" },
  BLAST_RADIUS: { label: "Blast Radius", icon: GitBranch, color: "text-amber-400" },
  SHADOW_SIM_REJECTED: { label: "Shadow Sim — Rejected", icon: XCircle, color: "text-rose-400" },
  SHADOW_SIM_APPROVED: { label: "Shadow Sim — Approved", icon: CheckCircle2, color: "text-emerald-400" },
  EXECUTED_REMEDIATION: { label: "Executed Remediation", icon: ShieldAlert, color: "text-emerald-400" },
  COMPANY_BRAIN_NOTIFY: { label: "Company Brain Notify", icon: User, color: "text-blue-400" },
};

function SimCard({
  title,
  result,
  accent,
}: {
  title: string;
  result?: ShadowSimResult;
  accent: "rose" | "emerald";
}) {
  if (!result) {
    return (
      <div className="flex-1 rounded-lg border border-dashed border-slate-800 p-2.5 text-[11px] text-slate-500">
        {title}
        <div className="mt-1">Awaiting simulation…</div>
      </div>
    );
  }
  const blocked = result.verdict === "REJECTED";
  return (
    <div
      className={cn(
        "flex-1 rounded-lg border p-2.5",
        accent === "rose"
          ? "border-rose-800/70 bg-rose-950/30"
          : "border-emerald-800/70 bg-emerald-950/30"
      )}
    >
      <div className="flex items-center gap-1.5">
        {blocked ? (
          <XCircle className="h-3.5 w-3.5 text-rose-400" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
        )}
        <span className="text-[11px] font-bold text-slate-200">{title}</span>
      </div>
      <div className="mt-1 font-mono text-[11px] text-slate-300">
        {result.action}
      </div>
      <div className="mt-1 text-[11px] leading-snug text-slate-400">
        {blocked ? (
          <>
            Orphaned flows:{" "}
            <span className="font-mono text-rose-300">
              {(result.orphaned_flows ?? []).join(", ") || "—"}
            </span>
            <br />
            Projected loss:{" "}
            <span className="font-mono font-bold text-rose-300">
              ${((result.projected_revenue_loss_per_min ?? 0)).toLocaleString()}/min
            </span>
          </>
        ) : (
          <>
            0 orphaned flows
            <br />
            Projected loss:{" "}
            <span className="font-mono font-bold text-emerald-300">$0/min</span>
          </>
        )}
      </div>
      <div className="mt-1 font-mono text-[10px] text-slate-500">
        {result.shadow_graph} · clone {result.clone_time_ms ?? "?"}ms
      </div>
    </div>
  );
}

function StepRow({
  ev,
  onHighlight,
}: {
  ev: TraceEvent;
  onHighlight: (ev: TraceEvent) => void;
}) {
  const [open, setOpen] = useState(false);
  const meta = PHASE_META[ev.phase] ?? {
    label: ev.phase,
    icon: Cpu,
    color: "text-slate-400",
  };
  const Icon = meta.icon;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-3.5 w-3.5 shrink-0", meta.color)} />
        <span className="text-[11px] font-semibold text-slate-200">
          <span className="mr-1 font-mono text-slate-500">#{ev.step_number}</span>
          {meta.label}
        </span>
        {ev.execution_time_ms !== undefined && ev.execution_time_ms !== null && (
          <span className="ml-auto shrink-0 rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
            {Number(ev.execution_time_ms).toFixed(1)}ms
          </span>
        )}
      </div>
      <div className="mt-1 truncate font-mono text-[10px] text-slate-500">
        MCP: {ev.mcp_tool_name}
      </div>

      {/* Phase-specific summaries */}
      {ev.phase === "GRAPH_DIAGNOSIS" && ev.root_cause && (
        <div className="mt-1.5 text-[11px] text-slate-300">
          Root cause:{" "}
          <span className="font-mono font-bold text-rose-300">
            {String(ev.root_cause.service_id ?? ev.root_cause.service_name ?? "")}
          </span>
          {ev.root_cause.commit_hash ? (
            <span className="font-mono text-slate-400">
              {" "}· commit {String(ev.root_cause.commit_hash).slice(0, 7)}
            </span>
          ) : null}
          {ev.root_cause.responsible_engineer ? (
            <span className="text-slate-400">
              {" "}· {String(ev.root_cause.responsible_engineer)}
            </span>
          ) : null}
        </div>
      )}
      {ev.phase === "BLAST_RADIUS" && (
        <div className="mt-1.5 text-[11px] text-slate-300">
          {(ev.impacted_flows ?? []).length} flow(s) impacted ·{" "}
          <span className="font-mono font-bold text-amber-300">
            ${((ev.revenue_at_risk_per_min ?? 0)).toLocaleString()}/min at risk
          </span>
        </div>
      )}
      {(ev.phase === "SHADOW_SIM_REJECTED" || ev.phase === "SHADOW_SIM_APPROVED") &&
        ev.candidate && (
          <div className="mt-1.5 text-[11px] text-slate-300">
            <span className="font-mono">{ev.candidate.action}</span> →{" "}
            <span
              className={cn(
                "font-bold",
                ev.verdict === "REJECTED" ? "text-rose-400" : "text-emerald-400"
              )}
            >
              {ev.verdict}
            </span>
          </div>
        )}
      {ev.phase === "EXECUTED_REMEDIATION" && ev.executed_action && (
        <div className="mt-1.5 text-[11px] text-emerald-300">
          ✓ Applied {ev.executed_action.action} to prod_graph
        </div>
      )}

      <div className="mt-1.5 flex gap-1.5">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1 rounded border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-300 hover:border-slate-500"
        >
          <ChevronDown
            className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
          />
          Inspect Cypher
        </button>
        {ev.proof_path.length > 0 && (
          <button
            onClick={() => onHighlight(ev)}
            className="flex items-center gap-1 rounded border border-cyan-800 bg-cyan-950/40 px-1.5 py-0.5 text-[10px] text-cyan-300 hover:border-cyan-600"
          >
            <Route className="h-3 w-3" />
            Highlight Path
          </button>
        )}
      </div>
      {open && (
        <pre className="slim-scroll mt-1.5 max-h-44 overflow-auto rounded bg-slate-950 p-2 font-mono text-[10px] leading-relaxed text-cyan-200/90">
          {ev.cypher_executed || "(no cypher captured for this step)"}
        </pre>
      )}
    </div>
  );
}

export default function AgentTracePanel({
  trace,
  shadowComparison,
  ownership,
  onHighlightStep,
}: Props) {
  const showDuel =
    trace.some((t) => t.phase === "SHADOW_SIM_REJECTED") || shadowComparison.rejected;

  return (
    <aside className="flex w-96 shrink-0 flex-col gap-3 overflow-y-auto border-l border-slate-800 bg-slate-950/60 p-3 slim-scroll">
      <section>
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Shadow-Graph Simulation Duel
        </h2>
        {showDuel ? (
          <div className="flex gap-2">
            <SimCard
              title="Naive action"
              result={shadowComparison.rejected}
              accent="rose"
            />
            <SimCard
              title="Surgical action"
              result={shadowComparison.approved}
              accent="emerald"
            />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-slate-800 p-3 text-center text-[11px] text-slate-500">
            The agent tests every candidate action in isolated FalkorDB shadow
            graphs before touching production. The duel appears here.
          </div>
        )}
      </section>

      <section className="flex min-h-0 flex-1 flex-col">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Agent Reasoning Trace
        </h2>
        {trace.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-3 text-center text-[11px] text-slate-500">
            Inject chaos, then run the agent.
            <br />
            Every MCP tool call, Cypher query and proof path streams here live.
          </div>
        ) : (
          <div className="flex flex-col gap-2 overflow-y-auto pr-0.5 slim-scroll">
            {trace.map((ev, i) => (
              <StepRow
                key={`${ev.step_number}-${i}`}
                ev={ev}
                onHighlight={onHighlightStep}
              />
            ))}
          </div>
        )}
      </section>

      {ownership && (
        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Company Brain — Ownership
          </h2>
          <div className="rounded-lg border border-blue-900/60 bg-blue-950/30 p-2.5">
            <div className="flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-blue-400" />
              <span className="font-mono text-[12px] font-bold text-blue-300">
                {ownership.owner_name ?? ownership.owner ?? ownership.author ?? "—"}
              </span>
              {(ownership.owner || ownership.author) && (
                <span className="font-mono text-[10px] text-slate-500">
                  @{ownership.owner ?? ownership.author}
                </span>
              )}
            </div>
            <div className="mt-1 text-[11px] text-slate-400">
              Service <span className="font-mono text-slate-300">{ownership.service}</span>
              {ownership.author && ownership.author !== ownership.owner && (
                <> · commit authored by <span className="font-mono">@{ownership.author}</span></>
              )}
            </div>
            {ownership.runbook?.title && (
              <div className="mt-1 text-[11px] text-slate-400">
                Runbook:{" "}
                <span className="text-slate-200">{ownership.runbook.title}</span>
                {ownership.runbook.action && (
                  <span className="font-mono text-[10px] text-slate-500">
                    {" "}· {ownership.runbook.action}
                  </span>
                )}
              </div>
            )}
            <div className="mt-1.5 rounded bg-slate-950/70 px-2 py-1 font-mono text-[10px] text-slate-500">
              → {ownership.channel ?? "notify:owner"} · {ownership.action_taken}
            </div>
          </div>
        </section>
      )}
    </aside>
  );
}
