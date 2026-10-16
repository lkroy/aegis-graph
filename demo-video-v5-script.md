# AegisGraph Demo Video v5 — Natural Guided Tour
# Tone: conversational, like a founder walking judges through the live product.
# Structure: problem → live walkthrough → architecture → close. Under 3:00.

## Part 1 — WHAT WE'RE SOLVING (~35s)
"Every engineering team knows this pain. It's 3 AM, checkout goes down, and you're staring at forty dashboards — each screaming a different symptom. But here's the thing: in a microservices world, the service that's screaming is almost never the service that's broken. One bad commit, five hops upstream, cascades through pricing, payments, checkout. Finding it takes engineers up to an hour. And the obvious fix — killing the failing service — can orphan the very flows you're trying to save."

## Part 2 — LIVE WALKTHROUGH (~95s)
"So we built AegisGraph. Let me show you the live demo — link below. This is a forty-three node production topology, living inside FalkorDB. Not a diagram — it's the agent's world model: business flows, services, databases, deploy commits, and the engineers who own them.

Watch what happens when I inject a poison-pill commit. The cascade — five hops upstream — seven services down, seventy-five hundred dollars a minute at risk.

Now I run the autonomous agent. First, it checks its episodic memory — seen this before? Then PageRank over the call graph — real Cypher — finds the culprit: a regex commit on the FX rate service. The Company Brain names the owner, Sarah Chen, and the runbook: rollback faulty deploy.

Now the key part. Before touching production, the agent clones the topology into isolated shadow graphs and duels two fixes. Killing the service? Rejected — it would orphan checkout flows. Rolling back the commit? Approved — zero projected impact.

The agent executes. The topology heals. The incident becomes a graph episode, so next time it remembers. And Sarah is notified, with evidence."

## Part 3 — ARCHITECTURE (~25s)
"Architecture is simple. One URL: CloudFront serves this dashboard from S3, routes API and WebSocket to FastAPI on EC2, with FalkorDB alongside. The agent is a seven-phase loop, and every phase is a Cypher query through MCP tools. No black boxes — ask why, and it shows you the graph path."

## Part 4 — CLOSE (~12s)
"That's AegisGraph. The future of reliability isn't faster dashboards — it's systems that reason about themselves, and can prove they're right."
