"""Render AegisGraph dashboard frames from live FalkorDB data for the demo video."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

COLORS = {
    'BusinessFlow': '#fbbf24',  # gold
    'Service_healthy': '#34d399',  # emerald
    'Service_bad': '#f43f5e',  # crimson
    'Database': '#a78bfa',  # purple
    'Database_bad': '#f43f5e',
    'Commit': '#22d3ee',  # cyan
    'Engineer': '#60a5fa',  # blue
    'Runbook': '#94a3b8',
    'IncidentEpisode': '#f472b6',
}

def load(stage):
    with open(f'/tmp/{stage}.json') as f:
        return json.load(f)

def build_graph(data):
    G = nx.DiGraph()
    for n in data['nodes']:
        G.add_node(n['id'], label=n['label'], name=n['name'],
                   status=n.get('status', 'HEALTHY'), props=n.get('props', {}))
    for l in data['links']:
        if l.get('source') and l.get('target'):
            G.add_edge(l['source'], l['target'], type=l.get('type', ''))
    return G

def node_color(d):
    label = d['label']
    status = d.get('status', 'HEALTHY')
    if label == 'Service':
        return COLORS['Service_bad'] if status in ('DEGRADED', 'DOWN', 'OFFLINE') else COLORS['Service_healthy']
    if label == 'Database':
        return COLORS['Database_bad'] if status in ('SATURATED', 'DOWN') else COLORS['Database']
    return COLORS.get(label, '#94a3b8')

def render(stage, title, subtitle, highlight_path=None, out=None):
    data = load(stage)
    G = build_graph(data)
    # Only show the core topology (flows, services, databases) for clarity
    keep = [n for n, d in G.nodes(data=True)
            if d['label'] in ('BusinessFlow', 'Service', 'Database')]
    H = G.subgraph(keep).copy()

    fig, ax = plt.subplots(figsize=(16, 9), facecolor='#020617')
    ax.set_facecolor('#020617')

    # Layered layout by tier / type
    pos = {}
    flows = [n for n in H.nodes if H.nodes[n]['label'] == 'BusinessFlow']
    dbs = [n for n in H.nodes if H.nodes[n]['label'] == 'Database']
    svcs = [n for n in H.nodes if H.nodes[n]['label'] == 'Service']
    for i, n in enumerate(flows):
        pos[n] = (2 + i * 6, 8)
    for i, n in enumerate(sorted(dbs)):
        pos[n] = (2 + i * 3.2, 0.5)
    # services by tier
    by_tier = {}
    for n in svcs:
        t = H.nodes[n].get('props', {}).get('tier', 2)
        by_tier.setdefault(t, []).append(n)
    for tier in sorted(by_tier):
        nodes = sorted(by_tier[tier])
        y = 6.5 - (tier - 1) * 1.5
        for i, n in enumerate(nodes):
            pos[n] = (1 + i * (14 / max(1, len(nodes) - 1)), y)

    # edges
    edge_colors = []
    for u, v in H.edges():
        if highlight_path and u in highlight_path and v in highlight_path:
            iu, iv = highlight_path.index(u), highlight_path.index(v)
            edge_colors.append('#22d3ee' if abs(iu - iv) == 1 else '#1e293b')
        else:
            edge_colors.append('#1e293b')
    nx.draw_networkx_edges(H, pos, ax=ax, edge_color=edge_colors,
                           width=1.2, alpha=0.7, arrows=False)

    # highlight path edges thicker
    if highlight_path:
        hp_edges = [(highlight_path[i], highlight_path[i+1])
                    for i in range(len(highlight_path)-1)
                    if H.has_edge(highlight_path[i], highlight_path[i+1])]
        nx.draw_networkx_edges(H, pos, ax=ax, edgelist=hp_edges,
                               edge_color='#22d3ee', width=3.5, alpha=0.95, arrows=False)

    # nodes
    for n in H.nodes():
        d = H.nodes[n]
        c = node_color(d)
        x, y = pos[n]
        size = 420 if d['label'] == 'BusinessFlow' else 300
        # glow for bad nodes
        if d.get('status') in ('DEGRADED', 'DOWN', 'OFFLINE', 'SATURATED'):
            ax.scatter([x], [y], s=size*2.2, c='#f43f5e', alpha=0.25, zorder=1)
        if highlight_path and n in highlight_path:
            ax.scatter([x], [y], s=size*1.8, c='#22d3ee', alpha=0.3, zorder=1)
        ax.scatter([x], [y], s=size, c=c, edgecolors='white',
                   linewidths=0.8, zorder=2)
        ax.text(x, y - 0.42, d['name'][:22], ha='center', va='top',
                fontsize=7, color='#e2e8f0', zorder=3)

    ax.text(0.5, 8.7, 'AegisGraph', fontsize=26, color='#f8fafc',
            weight='bold', va='top', ha='left', transform=ax.transData)
    ax.text(0.5, 8.25, title, fontsize=14, color='#22d3ee', va='top', ha='left')
    ax.text(0.5, 7.85, subtitle, fontsize=10, color='#94a3b8', va='top', ha='left')
    ax.set_xlim(-0.5, 16.5)
    ax.set_ylim(-0.5, 9.2)
    ax.axis('off')
    plt.tight_layout(pad=0.5)
    out = out or f'/tmp/frame_{stage}.png'
    plt.savefig(out, dpi=150, facecolor='#020617', bbox_inches='tight', pad_inches=0.1)
    plt.close()
    print('wrote', out)

if __name__ == '__main__':
    import sys
    stage, title, subtitle = sys.argv[1], sys.argv[2], sys.argv[3]
    hp = sys.argv[4].split(',') if len(sys.argv) > 4 and sys.argv[4] else None
    render(stage, title, subtitle, hp)
