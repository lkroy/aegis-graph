# AegisGraph Demo Video Script (max 3:00)

## Scene 1 — Hook (0:00–0:20)
**Visual:** Healthy dashboard, 43-node graph glowing.
**VO:** "When production breaks at 3 AM, dashboards show you symptoms — never causes. AegisGraph is an autonomous SRE agent that thinks in graphs. Every decision it makes is proven in FalkorDB before it touches production."

## Scene 2 — The topology (0:20–0:45)
**Visual:** Slow pan/zoom over the graph; highlight BusinessFlow gold nodes.
**VO:** "Forty-three nodes live in FalkorDB: revenue-generating business flows, microservices, databases, every deploy commit, and the engineers who own them. This isn't a visualization — it's the agent's world model."

## Scene 3 — Chaos (0:45–1:10)
**Visual:** Click "Poison-Pill Commit". Nodes cascade crimson. Revenue at Risk spikes to $7,500/min.
**VO:** "I inject a poison-pill commit. Watch the failure cascade five hops upstream — pricing, payments, checkout — $7,500 of revenue per minute at risk. A human would take an hour to untangle this."

## Scene 4 — Investigation (1:10–1:40)
**Visual:** Agent trace panel streaming; PageRank step highlighted; proof path animates on graph.
**VO:** "The agent queries its episodic memory, then runs PageRank over the call graph through MCP tools — real Cypher, real algorithms. It isolates the culprit: a regex commit on the FX rate service, authored by Sarah Chen. Every conclusion carries its proof path."

## Scene 5 — Shadow duel (1:40–2:20)
**Visual:** Side-by-side sim_rejected vs sim_approved; REJECTED/APPROVED verdicts.
**VO:** "Here's the killer feature. Before acting, the agent clones production into isolated shadow graphs and duels two fixes. Killing the service orphans EU checkout — rejected by the graph. Rolling back the commit proves zero impact — approved by the graph."

## Scene 6 — Resolution (2:20–2:45)
**Visual:** Graph heals green; episode in memory vault; notification card.
**VO:** "The approved fix executes. The topology heals, the incident is memorized as a graph episode for next time, and the owning engineer is notified — with evidence."

## Scene 7 — Close (2:45–3:00)
**Visual:** FalkorDB Browser showing the episode node; title card.
**VO:** "AegisGraph: multi-hop reasoning, graph algorithms as tools, actions proven before they're taken. FalkorDB isn't our database — it's the agent's brain."
