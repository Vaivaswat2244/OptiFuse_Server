# Will contain no_fusion, singleton, min_w_cut, greedy_tp, costless_csp

from ..core import *
from .metrics import calculate_metrics
import time
import itertools
from dataclasses import dataclass
from collections import defaultdict
import heapq
from typing import Tuple
from ..core.structures import Application, LambdaFunction

def no_fusion(app: Application) -> dict:
    start_time = time.time()
    groups = [[func] for func in app.functions]
    metrics = calculate_metrics(groups, app)
    return {'name': 'NoFusion', 'groups': groups, **metrics,
            'runtime': (time.time() - start_time) * 1000}


def singleton(app: Application) -> dict:
    start_time = time.time()
    q = [app.root_function]
    head = 0
    topo_sorted_funcs = []
    visited = {app.root_function.id}
    while head < len(q):
        node = q[head];
        head += 1
        topo_sorted_funcs.append(node)
        for child in node.children:
            if child.id not in visited:
                visited.add(child.id)
                q.append(child)

    groups = [topo_sorted_funcs]
    metrics = calculate_metrics(groups, app)
    return {'name': 'Singleton', 'groups': groups, **metrics,
            'runtime': (time.time() - start_time) * 1000}

def min_w_cut_heuristic(app: Application) -> dict:
        start_time = time.time()
        groups = [[f] for f in app.functions]
        merge_candidates = []
        for f in app.functions:
            for child in f.children:
                merge_candidates.append((f.get_data_transfer_cost(child.id), f, child))
        merge_candidates.sort(key=lambda x: x[0], reverse=True)

        for _, parent, child in merge_candidates:
            temp_group_map = {f.id: i for i, g in enumerate(groups) for f in g}
            parent_idx, child_idx = temp_group_map.get(parent.id), temp_group_map.get(child.id)

            if parent_idx is not None and child_idx is not None and parent_idx != child_idx:
                parent_group, child_group = groups[parent_idx], groups[child_idx]
                if sum(f.memory for f in parent_group) + sum(f.memory for f in child_group) <= app.max_memory:

                    groups[parent_idx].extend(child_group)
                    groups.pop(child_idx)
        metrics = calculate_metrics(groups, app)
        return {'name': 'MinWCut Heuristic', 'groups': groups, **metrics, 'runtime': (time.time() - start_time) * 1000}

def greedy_tree_partitioning(app: Application) -> dict:
        start_time = time.time()
        initial_cuts = set()
        critical_path = app.critical_path_functions
        critical_path_edges = list(zip(critical_path[:-1], critical_path[1:]))
        base_latency = sum(f.runtime for f in critical_path)
        if base_latency > app.max_latency:
             return {'name': 'Greedy TP (GrTP)', 'groups': [], 'cost': float('inf'), 'latency': base_latency, 'feasible': False, 'runtime': (time.time() - start_time) * 1000}

        for k in range(len(critical_path_edges) + 1):
            is_k_feasible = False
            for merge_combination in itertools.combinations(critical_path_edges, k):
                num_external_invocations = len(critical_path_edges) - len(merge_combination)
                current_latency = base_latency + num_external_invocations * app.network_hop_delay
                if current_latency <= app.max_latency:
                    initial_cuts = set(critical_path_edges) - set(merge_combination)
                    is_k_feasible = True
                    break
            if is_k_feasible:
                break

        initial_barrier_nodes = {app.root_function} | {child for _, child in initial_cuts}
        groups_dict = {b.id: [b] for b in initial_barrier_nodes}
        node_to_barrier_map = {b.id: b for b in initial_barrier_nodes}
        q = list(initial_barrier_nodes)
        head = 0
        while head < len(q):
            current_node = q[head]; head += 1
            barrier_node = node_to_barrier_map[current_node.id]
            for child in current_node.children:
                if child.id not in node_to_barrier_map:
                    node_to_barrier_map[child.id] = barrier_node
                    groups_dict[barrier_node.id].append(child)
                    q.append(child)

        groups = list(groups_dict.values())
        merge_candidates = []
        for f in app.functions:
            for child in f.children:
                if (f, child) not in initial_cuts:
                    merge_candidates.append((f.get_data_transfer_cost(child.id), f, child))
        merge_candidates.sort(key=lambda x: x[0], reverse=True)

        for _, parent, child in merge_candidates:
            temp_group_map = {f.id: i for i, g in enumerate(groups) for f in g}
            parent_idx, child_idx = temp_group_map.get(parent.id), temp_group_map.get(child.id)
            if parent_idx is not None and child_idx is not None and parent_idx != child_idx:
                parent_group, child_group = groups[parent_idx], groups[child_idx]
                if sum(f.memory for f in parent_group) + sum(f.memory for f in child_group) <= app.max_memory:
                    groups[parent_idx].extend(child_group)
                    groups.pop(child_idx)

        metrics = calculate_metrics(groups, app)
        return {'name': 'Greedy TP (GrTP)', 'groups': groups, **metrics, 'runtime': (time.time() - start_time) * 1000}

def costless_csp(app: Application) -> dict:
        start_time = time.time()
        chain = app.critical_path_functions
        if not chain: return {'name': 'Costless (CSP)', 'groups': [], 'feasible': False, 'error': 'No critical path.'}

        @dataclass
        class CSPLabel:
            cost: float; latency: int; current_group_mem: int; partitioning: Tuple[Tuple[LambdaFunction, ...], ...]
            def __lt__(self, other): return self.cost < other.cost

        labels = defaultdict(list)
        pq = []
        start_node = chain[0]
        initial_label = CSPLabel(cost=0, latency=start_node.runtime, current_group_mem=start_node.memory, partitioning=((start_node,),))
        labels[start_node.id].append(initial_label)
        heapq.heappush(pq, (initial_label.cost, start_node.id, initial_label))

        while pq:
            _, u_id, u_label = heapq.heappop(pq)
            u = app.functions_map[u_id]
            u_index = chain.index(u)
            if u_index + 1 >= len(chain): continue
            v = chain[u_index + 1]

            if u_label.current_group_mem + v.memory <= app.max_memory:
                new_part_merge = list(u_label.partitioning); new_part_merge[-1] += (v,)
                new_label_merge = CSPLabel(cost=u_label.cost, latency=u_label.latency + v.runtime, current_group_mem=u_label.current_group_mem + v.memory, partitioning=tuple(new_part_merge))
                if not any(l.cost <= new_label_merge.cost and l.latency <= new_label_merge.latency for l in labels[v.id]):
                    labels[v.id] = [l for l in labels[v.id] if not (new_label_merge.cost <= l.cost and new_label_merge.latency <= l.latency)]
                    labels[v.id].append(new_label_merge)
                    heapq.heappush(pq, (new_label_merge.cost, v.id, new_label_merge))

            new_label_cut = CSPLabel(cost=u_label.cost + u.get_data_transfer_cost(v.id), latency=u_label.latency + v.runtime + app.network_hop_delay, current_group_mem=v.memory, partitioning=u_label.partitioning + ((v,),))
            if not any(l.cost <= new_label_cut.cost and l.latency <= new_label_cut.latency for l in labels[v.id]):
                labels[v.id] = [l for l in labels[v.id] if not (new_label_cut.cost <= l.cost and new_label_cut.latency <= l.latency)]
                labels[v.id].append(new_label_cut)
                heapq.heappush(pq, (new_label_cut.cost, v.id, new_label_cut))

        best_label = min([l for l in labels[chain[-1].id] if l.latency <= app.max_latency], key=lambda l: l.cost, default=None)
        if not best_label: return {'name': 'Costless (CSP)', 'groups': [], 'feasible': False, 'runtime': (time.time() - start_time) * 1000, 'error': 'Infeasible on critical path'}

        final_groups = [list(g) for g in best_label.partitioning]
        assigned_funcs = {f for g in final_groups for f in g}
        for func in app.functions:
            if func not in assigned_funcs: final_groups.append([func])

        metrics = calculate_metrics(final_groups, app)
        return {'name': 'Costless (CSP)', 'groups': final_groups, **metrics, 'runtime': (time.time() - start_time) * 1000}