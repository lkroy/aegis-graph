# AegisGraph Demo Video v3 Script — "The 3-Minute Judge Cut"
# Target: ~2:55 total (under the 3:00 limit)
# Structure: Problem → How it works → Architecture → Close

## Clip 1 — PROBLEM (problem visual, ~44s)
"It's 3 AM. Checkout is down. Revenue is burning — thousands of dollars a minute. And you're staring at forty dashboards, each screaming a different symptom. Here's the brutal truth: in a microservices world, the service that's screaming is almost never the service that's broken. A bad commit five hops upstream cascades through pricing, payments, and checkout — while every team points at a different dashboard. Engineers take thirty to sixty minutes just to find the culprit. And the first instinct — kill the failing service — can orphan the very flows you're trying to save. What if your infrastructure could diagnose itself? And prove its fix is safe before touching production?"

## Clip 2 — MEET AEGISGRAPH + CHAOS (screenshot healthy → chaos, ~29s)
"Meet AegisGraph — an autonomous SRE agent that thinks in graphs. Its entire world lives in FalkorDB: forty-three nodes — business flows, microservices, databases, every deploy commit, and the engineers who own them. Not a visualization. A world model. Watch what happens when I inject a poison-pill commit. The failure cascades five hops upstream. Pricing, payments, checkout — seventy-five hundred dollars a minute at risk, seven nodes degraded."

## Clip 3 — INVESTIGATION (screenshot trace, ~17s)
"The agent takes over. First, episodic memory — has it seen this before? Then PageRank over the call graph — real algorithms, real Cypher — isolating the culprit: a regex commit on the FX rate service, authored by Sarah Chen. Every conclusion carries its proof path."

## Clip 4 — SHADOW DUEL (screenshot trace, ~17s)
"Now the killer feature. Before acting, the agent clones production into isolated shadow graphs and duels two candidate fixes. Killing the service orphans all three checkout flows — rejected by the graph. Rolling back the commit — approved, with zero projected impact."

## Clip 5 — RESOLUTION (screenshot healed, ~14s)
"The approved fix executes. The topology heals. The incident is stored as a graph episode — so next time, the agent remembers. And the owning engineer is notified, with evidence."

## Clip 6 — ARCHITECTURE (architecture diagram, ~42s)
"Three tiers, one URL. CloudFront serves the dashboard from S3, and routes API and WebSocket traffic to FastAPI on EC2 — with FalkorDB running alongside it. The agent itself is a deterministic seven-phase loop, and every single phase is a Cypher query executed through MCP tools. Memory, diagnosis, blast radius, the shadow duel, execution, notification. No black boxes. Every action is explainable through the graph paths that justified it. FalkorDB isn't our database. It's the agent's memory, its simulator, and its courtroom — where every fix must prove its innocence before it ships."

## Clip 7 — CLOSE (end card, ~15s)
"Three tracks, one graph: connected action, agent memory, and the company brain. The future of reliability isn't faster dashboards. It's systems that reason about themselves — and can prove they're right. AegisGraph. Think in graphs."
