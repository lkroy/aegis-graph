"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphLink, GraphNode, NodeLabel } from "@/types/graph";

/* Minimal prop surface we use from react-force-graph-2d (typed loosely to
   keep the build clean across library versions). */
interface ForceGraphProps {
  graphData: { nodes: GraphNode[]; links: GraphLink[] };
  nodeIdAccessor?: (n: GraphNode) => string;
  nodeLabel?: (n: GraphNode) => string;
  nodeCanvasObject?: (n: GraphNode, ctx: CanvasRenderingContext2D, g: number) => void;
  nodeCanvasObjectMode?: () => string;
  nodePointerAreaPaint?: (n: GraphNode, color: string, ctx: CanvasRenderingContext2D) => void;
  linkColor?: (l: GraphLink) => string;
  linkWidth?: (l: GraphLink) => number;
  linkDirectionalParticles?: (l: GraphLink) => number;
  linkDirectionalParticleColor?: () => string;
  linkDirectionalParticleWidth?: number;
  linkDirectionalParticleSpeed?: number;
  linkHoverPrecision?: number;
  onNodeClick?: (n: GraphNode) => void;
  onNodeHover?: (n: GraphNode | null) => void;
  cooldownTicks?: number;
  d3AlphaDecay?: number;
  d3VelocityDecay?: number;
  backgroundColor?: string;
  ref?: React.Ref<ForceGraphHandle>;
}
interface ForceGraphHandle {
  refresh: () => void;
  zoomToFit: (ms?: number, px?: number) => void;
}

const ForceGraph2D = dynamic(
  () => import("react-force-graph-2d").then((m) => m.default),
  { ssr: false }
) as unknown as React.ComponentType<ForceGraphProps>;

const LABEL_COLORS: Record<NodeLabel, string> = {
  BusinessFlow: "#fbbf24",
  Service: "#34d399",
  Database: "#a78bfa",
  Commit: "#22d3ee",
  Engineer: "#60a5fa",
  Runbook: "#fb923c",
  IncidentEpisode: "#f472b6",
};

const BAD_STATUSES = new Set([
  "DEGRADED",
  "DOWN",
  "AT_RISK",
  "SATURATED",
  "OFFLINE",
]);

function nodeColor(n: GraphNode): string {
  if (BAD_STATUSES.has(n.status)) return "#f43f5e";
  if (n.label === "Commit" && n.props?.is_buggy && n.props?.is_active)
    return "#f43f5e";
  return LABEL_COLORS[n.label] ?? "#94a3b8";
}

function nodeRadius(n: GraphNode): number {
  switch (n.label) {
    case "BusinessFlow":
      return 11;
    case "Database":
      return 9;
    case "Service":
      return 7;
    case "Engineer":
      return 7;
    case "Runbook":
      return 6;
    case "IncidentEpisode":
      return 6;
    case "Commit":
      return 4;
    default:
      return 6;
  }
}

function drawShape(
  ctx: CanvasRenderingContext2D,
  n: GraphNode,
  x: number,
  y: number,
  r: number
) {
  ctx.beginPath();
  switch (n.label) {
    case "BusinessFlow": {
      // hexagon
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + r * Math.cos(a);
        const py = y + r * Math.sin(a);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      break;
    }
    case "Database": {
      // rounded rect (cylinder-ish)
      const w = r * 1.7;
      const h = r * 1.5;
      const rr = 3;
      ctx.moveTo(x - w / 2 + rr, y - h / 2);
      ctx.arcTo(x + w / 2, y - h / 2, x + w / 2, y + h / 2, rr);
      ctx.arcTo(x + w / 2, y + h / 2, x - w / 2, y + h / 2, rr);
      ctx.arcTo(x - w / 2, y + h / 2, x - w / 2, y - h / 2, rr);
      ctx.arcTo(x - w / 2, y - h / 2, x + w / 2, y - h / 2, rr);
      ctx.closePath();
      break;
    }
    case "Engineer": {
      // triangle
      ctx.moveTo(x, y - r);
      ctx.lineTo(x + r * 0.95, y + r * 0.8);
      ctx.lineTo(x - r * 0.95, y + r * 0.8);
      ctx.closePath();
      break;
    }
    case "Runbook": {
      // diamond
      ctx.moveTo(x, y - r);
      ctx.lineTo(x + r, y);
      ctx.lineTo(x, y + r);
      ctx.lineTo(x - r, y);
      ctx.closePath();
      break;
    }
    case "Commit": {
      // small square
      ctx.rect(x - r, y - r, r * 2, r * 2);
      break;
    }
    default:
      ctx.arc(x, y, r, 0, 2 * Math.PI);
  }
}

interface Props {
  nodes: GraphNode[];
  links: GraphLink[];
  highlighted: Set<string>;
  proofPath: string[];
}

function linkKey(a: string, b: string): string {
  return `${a}>${b}`;
}

export default function GraphCanvas({
  nodes,
  links,
  highlighted,
  proofPath,
}: Props) {
  const fgRef = useRef<ForceGraphHandle>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [hovered, setHovered] = useState<GraphNode | null>(null);

  // Proof-path edge lookup: consecutive ordered pairs (+ reverse for safety).
  const proofEdges = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i + 1 < proofPath.length; i++) {
      s.add(linkKey(proofPath[i], proofPath[i + 1]));
      s.add(linkKey(proofPath[i + 1], proofPath[i]));
    }
    return s;
  }, [proofPath]);

  // Repaint loop so the degraded-node halo pulses and particles animate.
  useEffect(() => {
    const id = window.setInterval(() => fgRef.current?.refresh(), 60);
    return () => window.clearInterval(id);
  }, []);

  // Refit on data change.
  const dataSig = `${nodes.length}:${links.length}`;
  useEffect(() => {
    const t = window.setTimeout(() => fgRef.current?.zoomToFit(400, 40), 600);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataSig]);

  const nodeCanvasObject = (n: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const x = n.x ?? 0;
    const y = n.y ?? 0;
    const r = nodeRadius(n);
    const color = nodeColor(n);
    const bad = BAD_STATUSES.has(n.status);

    // Pulsing crimson halo for degraded/down nodes.
    if (bad) {
      const t = Date.now() / 350;
      const pulse = 3 + 2.5 * Math.sin(t);
      ctx.beginPath();
      ctx.arc(x, y, r + 5 + pulse, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(244,63,94,0.55)";
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x, y, r + 9 + pulse * 1.4, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(244,63,94,0.18)";
      ctx.lineWidth = 5;
      ctx.stroke();
    }

    // Gold ring for agent-highlighted nodes.
    if (highlighted.has(n.id)) {
      ctx.beginPath();
      ctx.arc(x, y, r + 4, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(251,191,36,0.9)";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Body.
    drawShape(ctx, n, x, y, r);
    ctx.fillStyle = color;
    ctx.globalAlpha = bad ? 0.95 : 0.85;
    ctx.fill();
    ctx.globalAlpha = 1;
    if (selected?.id === n.id || hovered?.id === n.id) {
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Text label underneath.
    const fontSize = Math.max(11 / globalScale, 3.5);
    ctx.font = `600 ${fontSize}px ui-monospace, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = bad ? "#fda4af" : "#cbd5e1";
    ctx.fillText(n.name || n.id, x, y + r + 4);
  };

  const nodePointerAreaPaint = (
    n: GraphNode,
    color: string,
    ctx: CanvasRenderingContext2D
  ) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(n.x ?? 0, n.y ?? 0, nodeRadius(n) + 4, 0, 2 * Math.PI);
    ctx.fill();
  };

  const edgeInProof = (l: GraphLink): boolean => {
    const s = typeof l.source === "object" ? (l.source as unknown as GraphNode).id : (l.source as string);
    const t = typeof l.target === "object" ? (l.target as unknown as GraphNode).id : (l.target as string);
    return proofEdges.has(linkKey(s, t));
  };

  return (
    <div className="relative h-full w-full">
      <ForceGraph2D
        ref={fgRef}
        graphData={{ nodes, links }}
        nodeIdAccessor={(n) => n.id}
        nodeLabel={() => ""}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => "replace"}
        nodePointerAreaPaint={nodePointerAreaPaint}
        linkColor={(l) =>
          edgeInProof(l) ? "#22d3ee" : "rgba(100,116,139,0.55)"
        }
        linkWidth={(l) => (edgeInProof(l) ? 3 : 1)}
        linkDirectionalParticles={(l) => (edgeInProof(l) ? 4 : 0)}
        linkDirectionalParticleColor={() => "#22d3ee"}
        linkDirectionalParticleWidth={3}
        linkDirectionalParticleSpeed={0.006}
        linkHoverPrecision={6}
        onNodeClick={(n) => setSelected((prev) => (prev?.id === n.id ? null : n))}
        onNodeHover={(n) => setHovered(n)}
        cooldownTicks={120}
        d3AlphaDecay={0.022}
        d3VelocityDecay={0.3}
        backgroundColor="rgba(0,0,0,0)"
      />

      {nodes.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="rounded-lg border border-dashed border-slate-700 bg-slate-900/70 px-4 py-3 text-center text-xs text-slate-400">
            This shadow graph is empty.
            <br />
            Run the agent to generate simulation graphs.
          </div>
        </div>
      )}

      {selected && (
        <div className="absolute bottom-3 left-3 max-w-xs rounded-lg border border-slate-700 bg-slate-900/95 p-3 shadow-xl">
          <div className="flex items-center justify-between gap-2">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: nodeColor(selected) }}
            />
            <span className="font-mono text-xs font-bold text-slate-100">
              {selected.id}
            </span>
            <button
              onClick={() => setSelected(null)}
              className="ml-auto text-slate-500 hover:text-slate-200"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div className="mt-1 text-[11px] text-slate-400">
            {selected.label} ·{" "}
            <span
              className={
                BAD_STATUSES.has(selected.status)
                  ? "font-semibold text-rose-400"
                  : "text-emerald-400"
              }
            >
              {selected.status}
            </span>
          </div>
          <pre className="slim-scroll mt-2 max-h-40 overflow-auto rounded bg-slate-950 p-2 font-mono text-[10px] leading-relaxed text-slate-400">
            {JSON.stringify(selected.props ?? {}, null, 1)}
          </pre>
        </div>
      )}

      {/* Legend */}
      <div className="absolute right-3 top-3 rounded-lg border border-slate-800 bg-slate-900/85 px-2.5 py-2">
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {(Object.keys(LABEL_COLORS) as NodeLabel[]).map((l) => (
            <div key={l} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: LABEL_COLORS[l] }}
              />
              <span className="text-[10px] text-slate-400">{l}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
