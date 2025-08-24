import yaml
from typing import Dict, Any
from .structures import Application, LambdaFunction

class ApplicationBuilder:
    """
    A builder class responsible for creating and modifying Application objects
    from a serverless.yml file and live performance data from AWS.
    """
    
    @staticmethod
    def create_from_yaml_content(repo_name: str, yaml_content: str) -> Application:
        """
        Parses a real serverless.yml content string to build a base Application object.
        It uses standard Serverless Framework keys and expects a custom block for topology.
        """
        try:
            spec = yaml.safe_load(yaml_content)
            if not isinstance(spec, dict):
                raise ValueError("YAML content does not represent a valid object (dictionary).")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML content: {e}")

        # Extract major sections from the YAML spec, providing empty dicts as defaults
        functions_spec = spec.get('functions', {})
        provider_spec = spec.get('provider', {})
        custom_spec = spec.get('custom', {})
        
        if not functions_spec:
            raise ValueError("No 'functions' block found in the serverless.yml file.")
            
        # --- First Pass: Create all LambdaFunction objects with their properties ---
        functions = {}
        for func_id, props in functions_spec.items():
            if not isinstance(props, dict):
                continue
            
            # Use specific memory/timeout if defined, otherwise fall back to provider default
            memory = props.get('memorySize', provider_spec.get('memorySize', 512))
            # Timeout is in seconds in serverless.yml, convert to ms
            timeout_sec = props.get('timeout', provider_spec.get('timeout', 30))
            
            functions[func_id] = LambdaFunction(
                id=func_id,
                name=func_id, # We will use the function ID as the primary name
                memory=memory,
                baseline_runtime=timeout_sec * 1000 # Use timeout as a rough baseline
            )
        
        # --- Second Pass: Build the dependency graph from the custom topology block ---
        # This requires the user to define the graph structure in their YAML
        # Example:
        # custom:
        #   optifuse:
        #     topology:
        #       upload: { children: { resize: 5242880, filter: 5242880 } }
        #       resize: { children: { watermark: 2097152 } }
        optifuse_config = custom_spec.get('optifuse', {})
        topology = optifuse_config.get('topology', {})
        
        for parent_id, details in topology.items():
            if parent_id in functions and isinstance(details, dict) and 'children' in details:
                for child_id, data_bytes in details['children'].items():
                    if child_id in functions:
                        # Build the parent-child relationship
                        functions[parent_id].add_child(functions[child_id], data_bytes)
        
        # --- Extract constraints and critical path from the custom block ---
        constraints = optifuse_config.get('constraints', {})
        
        return Application(
            name=repo_name,
            functions=list(functions.values()),
            critical_path_ids=optifuse_config.get('criticalPath', []),
            max_memory=constraints.get('maxMemoryMB', 1024),
            max_latency=constraints.get('maxLatencyMS', 30000),
            network_hop_delay=constraints.get('networkHopMS', 20) # A more realistic default
        )

    @staticmethod
    def enrich_with_live_data(app: Application, live_metrics: Dict[str, Any]) -> Application:
        """
        Updates an existing Application object with live performance metrics from AWS.
        It matches functions by their ID (e.g., 'orderPlaced') and updates their
        runtime and memory properties with the measured averages.
        """
        # Create a map of function IDs to LambdaFunction objects for efficient lookup
        func_id_map = {func.id: func for func in app.functions}

        for func_id_from_aws, metrics in live_metrics.items():
            # Find the corresponding function in our application model
            if func_id_from_aws in func_id_map:
                target_func = func_id_map[func_id_from_aws]
                
                # Update the object's properties with the real, measured data
                target_func.baseline_runtime = metrics.get('avg_runtime_ms', target_func.baseline_runtime)
                target_func.memory = metrics.get('avg_memory_mb', target_func.memory)
        
        return app