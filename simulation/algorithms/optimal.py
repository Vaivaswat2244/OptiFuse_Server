# Will contain mtx_ilp
import pulp
from ..core import Application
import time
from collections import defaultdict
from metrics import calculate_metrics

def mtx_ilp(app: Application) -> dict:
        start_time = time.time()
        if not pulp: return {'name': 'MtxILP (Optimal)', 'feasible': False, 'runtime': 0, 'error': 'pulp not installed'}

        prob = pulp.LpProblem("Fusion_MtxILP", pulp.LpMinimize)
        roots = app.functions
        x = pulp.LpVariable.dicts("x", ((b.id, f.id) for b in roots for f in app.functions), cat='Binary')
        all_edges = [(u, v) for u in app.functions for v in u.children]
        is_cut = pulp.LpVariable.dicts("is_cut", ((e[0].id, e[1].id) for e in all_edges), cat='Binary')

        prob += pulp.lpSum(u.get_data_transfer_cost(v.id) * is_cut[u.id, v.id] for u, v in all_edges), "Minimize_Transfer_Cost"

        for f in app.functions: prob += pulp.lpSum(x[b.id, f.id] for b in roots) == 1, f"Assign_{f.id}"
        for b in roots:
            for f in app.functions:
                prob += x[b.id, f.id] <= x[b.id, b.id], f"Root_Integrity_{b.id}_{f.id}"
            prob += pulp.lpSum(f.memory * x[b.id, f.id] for f in app.functions) <= app.max_memory * x[b.id, b.id], f"Memory_{b.id}"
        for u, v in all_edges:
            for b in roots:
                prob += is_cut[u.id, v.id] >= x[b.id, u.id] - x[b.id, v.id], f"Cut_A_{b.id}_{u.id}_{v.id}"
                prob += is_cut[u.id, v.id] >= x[b.id, v.id] - x[b.id, u.id], f"Cut_B_{b.id}_{u.id}_{v.id}"

        critical_path_edges = list(zip(app.critical_path_functions[:-1], app.critical_path_functions[1:]))
        runtime_sum = sum(f.runtime for f in app.critical_path_functions)
        network_overhead = pulp.lpSum(app.network_hop_delay * is_cut[u.id, v.id] for u, v in critical_path_edges)
        prob += runtime_sum + network_overhead <= app.max_latency, "Latency_Constraint"

        prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=60))
        runtime = (time.time() - start_time) * 1000

        if pulp.LpStatus[prob.status] == 'Optimal':
            groups_dict = defaultdict(list)
            for b in roots:
                if pulp.value(x[b.id, b.id]) > 0.5:
                    for f in app.functions:
                        if pulp.value(x[b.id, f.id]) > 0.5: groups_dict[b.id].append(app.functions_map[f.id])
            groups = list(groups_dict.values())
            metrics = calculate_metrics(groups, app)
            return {'name': 'MtxILP (Optimal)', 'groups': groups, **metrics, 'runtime': runtime}
        else:
            return {'name': 'MtxILP (Optimal)', 'groups': [], 'cost': float('inf'), 'latency': float('inf'), 'feasible': False, 'runtime': runtime, 'error': pulp.LpStatus[prob.status]}