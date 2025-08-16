# simulation/runner.py

from .core.structures import Application
from .algorithms import heuristics, optimal
# We need to install pulp for the optimal algorithm
# Run: pip install pulp
# Then: pip freeze > requirements.txt

def run_all_simulations(app: Application) -> list:
    """
    Runs a suite of fusion algorithms on a given application and returns the results.
    This function orchestrates the execution of all defined algorithms.
    """
    # A list of all the algorithm functions we want to run
    algorithms_to_run = [
        heuristics.no_fusion,
        heuristics.singleton,
        heuristics.min_w_cut_heuristic,
        heuristics.greedy_tree_partitioning,
        heuristics.costless_csp,
        optimal.mtx_ilp,
    ]

    results = []
    for alg_func in algorithms_to_run:
        try:
            # We get the function's name for clear labeling in the results
            func_name = getattr(alg_func, '__name__', 'Unknown Algorithm')
            
            # Execute the algorithm function, passing the Application object
            result = alg_func(app)
            
            # Ensure the result has a name, even if the function didn't provide one
            if 'name' not in result:
                result['name'] = func_name.replace('_', ' ').title()
                
            results.append(result)
        except Exception as e:
            # If any algorithm crashes, we catch the error and report it
            # without stopping the entire simulation.
            func_name = getattr(alg_func, '__name__', 'Unknown Algorithm')
            results.append({
                'name': func_name.replace('_', ' ').title(),
                'feasible': False,
                'error': f"Algorithm failed with exception: {e}"
            })
            
    # Sort the results for a clean presentation: feasible solutions first, then by cost
    results.sort(key=lambda x: (not x.get('feasible', False), x.get('cost', float('inf'))))
    
    return results