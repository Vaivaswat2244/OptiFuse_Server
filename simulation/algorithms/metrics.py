from ..core.structures import LambdaFunction, CompositeFunction, Application
from ..utils.group_map import _get_func_to_group_map
from typing import Any

def calculate_metrics(groups_of_funcs: list[list[LambdaFunction]], app: Application) -> \
dict[str, Any]:
    """
    REFactored metrics calculation based on the CompositeFunction model.
    This is the new "judge" that evaluates the output of all algorithms.
    """
    composite_groups = [CompositeFunction(g) for g in groups_of_funcs]
    func_to_composite_map = _get_func_to_group_map(composite_groups)

    total_cost = sum(group.get_execution_cost() for group in composite_groups)

    for func in app.functions:
        parent_group = func_to_composite_map.get(func.id)
        for child in func.children:
            child_group = func_to_composite_map.get(child.id)
            if parent_group and child_group and parent_group.id != child_group.id:
                total_cost += func.get_data_transfer_cost(child.id)

    latency = 0.0
    critical_path = app.critical_path_functions
    if critical_path:
        latency = sum(f.runtime for f in critical_path)
        for i in range(len(critical_path) - 1):
            parent, child = critical_path[i], critical_path[i + 1]
            parent_group = func_to_composite_map.get(parent.id)
            child_group = func_to_composite_map.get(child.id)
            if parent_group and child_group and parent_group.id != child_group.id:
                latency += app.network_hop_delay

    mem_feasible = all(group.memory <= app.max_memory for group in composite_groups)
    lat_feasible = latency <= app.max_latency
    is_feasible = mem_feasible and lat_feasible

    return {'cost': total_cost, 'latency': latency, 'feasible': is_feasible}