#!/usr/bin/env python3
"""AegisGraph system architecture diagram — dark SRE-console aesthetic.
Outputs a high-res PNG. Source of truth: README.md + backend/ layout."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

# ---------- palette ----------
BG      = "#0b0e14"
PANEL   = "#11161f"
PANEL2  = "#161d2a"
EDGE    = "#2a3444"
TXT     = "#e6edf3"
DIM     = "#9aa7b8"
CYAN    = "#22d3ee"   # FalkorDB / graph
VIOLET  = "#a78bfa"   # agent / MCP
AMBER   = "#f59e0b"   # chaos
GREEN   = "#34d399"   # approved / healthy
RED     = "#f87171"   # rejected / incident
BLUE    = "#60a5fa"   # frontend / UI

fig, ax = plt.subplots(figsize=(16, 11.5), dpi=200)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 1600)
ax.set_ylim(0, 1150)
ax.axis("off")


def box(x, y, w, h, face=PANEL, edge=EDGE, lw=1.6, rad=14):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=6,rounding_size={rad}",
                       facecolor=face, edgecolor=edge, linewidth=lw)
    ax.add_patch(p)


def title(x, y, s, size=17, color=TXT, ha="center"):
    ax.text(x, y, s, fontsize=size, color=color, weight="bold", ha=ha, va="center")


def body(x, y, s, size=12.5, color=DIM, ha="center", ls=1.5):
    ax.text(x, y, s, fontsize=size, color=color, ha=ha, va="center", linespacing=ls)


def mono(x, y, s, size=11.5, color=DIM, ha="center"):
    ax.text(x, y, s, fontsize=size, color=color, ha=ha, va="center", family="monospace")


def arrow(x1, y1, x2, y2, color=EDGE, lw=2.2, label=None, lcolor=DIM, dy=20):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                        linewidth=lw, color=color, shrinkA=2, shrinkB=7)
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, fontsize=11,
                color=lcolor, ha="center", va="center", family="monospace")


def badge(x, y, num, color):
    c = Circle((x, y), 24, facecolor=color, edgecolor="none", zorder=5)
    ax.add_patch(c)
    ax.text(x, y - 1, num, fontsize=16, color=BG, weight="bold",
            ha="center", va="center", zorder=6)


# ================= HEADER =================
title(800, 1105, "AegisGraph  —  Autonomous SRE & Chaos-Remediation Agent", size=27)
body(800, 1068, "FalkorDB  “Graph Hacks: Context for AI Agents”  ·  Track 01 — Act on Connected Data  ·  "
                 "Track 02 — Memory & Coordination  ·  Track 03 — Company Brain", size=13)

# ================= TOP: COMPONENTS =================
# ---- LEFT: Operator + Frontend ----
box(40, 700, 380, 330, edge=BLUE)
title(230, 1000, "Operator", size=16, color=BLUE)
body(230, 964, "clicks a chaos scenario\nwatches the live canvas", size=12)
box(62, 722, 336, 208, face=PANEL2, edge=BLUE)
title(230, 896, "Frontend — Next.js 14", size=15, color=BLUE)
mono(230, 866, ":3001 · SRE command center", color=BLUE)
body(230, 822, "WebSocket live canvas · tenant pills\nprod / sim_rejected / sim_approved\nanimated causal proof paths", size=11)

# ---- MIDDLE: Backend ----
box(460, 700, 560, 330, edge=VIOLET)
title(740, 1000, "Backend — FastAPI  :8000", size=16, color=VIOLET)
mono(740, 970, "REST + WebSocket", color=VIOLET)
box(482, 836, 516, 118, face=PANEL2, edge=VIOLET)
title(740, 928, "Agent Orchestrator", size=14, color=VIOLET)
body(740, 898, "deterministic remediation loop · agent/orchestrator.py", size=11)
mono(740, 868, "recall → localize → blast radius → duel → execute", size=11, color=CYAN)
box(482, 722, 250, 100, face=PANEL2, edge=AMBER)
title(607, 796, "Chaos Engine", size=13, color=AMBER)
body(607, 758, "poison-pill commit\nRedis pool exhaustion\npayment-gateway crash", size=10.5)
box(748, 722, 250, 100, face=PANEL2, edge=VIOLET)
title(873, 796, "Shadow Simulator", size=13, color=VIOLET)
body(873, 758, "multigraph clone\nSLA reachability Cypher", size=10.5)

# MCP strip
box(460, 566, 560, 104, face=PANEL2, edge=VIOLET)
title(740, 636, "FastMCP  :8001  (SSE)  —  6 real-Cypher tools", size=13, color=VIOLET)
mono(740, 606, "localize_root_cause · compute_blast_radius", size=10.5)
mono(740, 586, "detect_shared_bottleneck · discover_failover_route", size=10.5)
mono(740, 566, "simulate_candidate_action · recall_similar_incidents", size=10.5)

# ---- RIGHT: FalkorDB ----
box(1060, 580, 500, 450, edge=CYAN)
title(1310, 1000, "FalkorDB  :6379", size=16, color=CYAN)
mono(1310, 970, "the graph IS the system — not decoration", size=11.5, color=CYAN)
box(1082, 850, 456, 104, face=PANEL2, edge=CYAN)
title(1310, 928, "prod_graph — live topology", size=14, color=CYAN)
body(1310, 892, "43 nodes / 66 edges — services, DBs, commits,\nengineers, runbooks, business flows", size=11)
box(1082, 726, 222, 108, face=PANEL2, edge=RED)
title(1193, 802, "sim_rejected", size=13, color=RED)
body(1193, 764, "naive fix clone\norphans revenue flows", size=10.5)
box(1316, 726, 222, 108, face=PANEL2, edge=GREEN)
title(1427, 802, "sim_approved", size=13, color=GREEN)
body(1427, 764, "surgical fix clone\n$0 SLA impact", size=10.5)
box(1082, 600, 456, 110, face=PANEL2, edge=CYAN)
title(1310, 678, ":IncidentEpisode  memory", size=13, color=CYAN)
body(1310, 644, "every incident persisted — Track 02", size=11)

# ---- connections ----
arrow(420, 865, 460, 865, color=BLUE, label="WebSocket", lcolor=BLUE)
arrow(1020, 865, 1060, 865, color=CYAN, label="Cypher", lcolor=CYAN)
arrow(740, 700, 740, 670, color=VIOLET, label="MCP", lcolor=VIOLET, dy=20)
arrow(1020, 618, 1060, 618, color=CYAN, label="Cypher", lcolor=CYAN)
# chaos inject: operator UI -> chaos engine
arrow(420, 772, 482, 772, color=AMBER, label="chaos inject", lcolor=AMBER, dy=22)

# ================= BOTTOM: REMEDIATION LOOP =================
title(800, 520, "The autonomous remediation loop", size=19)
body(800, 492, "every agent action carries the exact ordered node / edge path it traversed", size=12)

steps = [
    ("1", "INJECT CHAOS", AMBER,
     "poison-pill commit\nRedis pool exhaustion\npayment-gateway crash"),
    ("2", "RECALL MEMORY", CYAN,
     "match :IncidentEpisode\nby failure signature"),
    ("3", "LOCALIZE CAUSE", VIOLET,
     "CALL algo.pageRank\ndeepest-fault boundary"),
    ("4", "BLAST RADIUS", VIOLET,
     "[:CALLS*1..6] traversal\ncausal_proof_path"),
    ("5", "SHADOW DUEL", RED,
     "clone to sim graphs\nSLA reachability"),
    ("6", "EXECUTE & LEARN", GREEN,
     "apply surgical fix\npersist + notify owner"),
]
sx0, sw, gap, sy, sh = 40, 218, 38, 130, 300
for i, (num, ttl, color, desc) in enumerate(steps):
    x = sx0 + i * (sw + gap)
    box(x, sy, sw, sh, edge=color, lw=2)
    badge(x + 36, sy + sh - 36, num, color)
    ax.text(x + 70, sy + sh - 36, ttl, fontsize=12, color=color, weight="bold",
            ha="left", va="center")
    body(x + sw / 2, sy + 150, desc, size=11.5)
    if i < len(steps) - 1:
        arrow(x + sw, sy + sh / 2, x + sw + gap, sy + sh / 2, color=color, lw=2.4)

# verdicts inside step 5 — plain colored text, no boxes
vx = sx0 + 4 * (sw + gap) + sw / 2
ax.text(vx, sy + 78, "✕  naive  →  REJECTED", fontsize=11, color=RED, ha="center",
        va="center", weight="bold")
ax.text(vx, sy + 44, "✓  surgical  →  APPROVED", fontsize=11, color=GREEN, ha="center",
        va="center", weight="bold")

# footer
mono(800, 60, "docker compose up   →   dashboard :3001  ·  api :8000  ·  FalkorDB browser :3000",
     size=12, color=DIM)
body(800, 28, "repo: github.com/lkroy/aegis-graph   ·   WeMakeDevs × FalkorDB  “Graph Hacks”  ·  submissions close Oct 18, 11:59 PM IST",
     size=11.5)

plt.tight_layout(pad=0.5)
plt.savefig("/home/hatch/workspace/your_files/aegisgraph-architecture.png",
            facecolor=BG, bbox_inches="tight")
print("saved")
