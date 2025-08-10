# Will contain the visualization logic
import matplotlib.pyplot as plt
from ..core import LambdaFunction, CompositeFunction
from ..utils import _get_func_to_group_map
import os
import networkx as nx
import numpy as np


def visualize_fusion(self, groups_of_funcs: list[list[LambdaFunction]], title: str,
                     filename: str):
    if not groups_of_funcs: return
    G = nx.DiGraph()
    all_funcs = [func for group in groups_of_funcs for func in group]

    composite_groups = [CompositeFunction(g) for g in groups_of_funcs]
    func_to_composite_map = _get_func_to_group_map(composite_groups)

    colors = plt.cm.viridis(np.linspace(0, 1, len(composite_groups)))

    for func in all_funcs:
        label = f"{func.name.split()[0]}\n({func.memory}MB, {func.runtime}ms)"
        group_obj = func_to_composite_map.get(func.id)
        group_idx = composite_groups.index(group_obj) if group_obj else -1
        G.add_node(func.id, label=label, group_id=group_idx)
    for func in all_funcs:
        for child in func.children:
            if child.id in G: G.add_edge(func.id, child.id)

    plt.figure(figsize=(14, 9))
    pos = nx.spring_layout(G, seed=42, k=1.5, iterations=70)

    valid_nodes = [node for node in G.nodes() if
                   0 <= G.nodes[node]['group_id'] < len(colors)]
    valid_colors = [colors[G.nodes[node]['group_id']] for node in valid_nodes]

    nx.draw_networkx_nodes(G, pos, nodelist=valid_nodes, node_size=3500,
                           node_color=valid_colors, node_shape='s', alpha=0.8)
    nx.draw_networkx_edges(G, pos, alpha=0.6, edge_color='gray', arrows=True,
                           arrowsize=20, node_size=3500)
    labels = {node: G.nodes[node]['label'] for node in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=9, font_color='black')
    plt.title(title, fontsize=18);
    plt.tight_layout()
    plt.savefig(os.path.join(self.output_dir, filename));
    plt.show()
    print(f"Saved fusion graph to: {os.path.join(self.output_dir, filename)}")