import yaml
from typing import Dict, Any
from .structures import Application, LambdaFunction

class ApplicationBuilder:
    """
    A builder class responsible for creating and modifying Application objects
    from different data sources like YAML files or live performance data.
    """
    
    @staticmethod
    def create_from_yaml_content(repo_name: str, yaml_content: str) -> Application:
        """
        Parses YAML content from a serverless.yml file to build a base Application object.
        """
        try:
            spec = yaml.safe_load(yaml_content)
            if not isinstance(spec, dict):
                raise ValueError("YAML content must be a dictionary.")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML content: {e}")

        functions_spec = spec.get('functions', {})
        constraints_spec = spec.get('constraints', {})
        
        if not functions_spec:
            raise ValueError("No 'functions' defined in the provided YAML content.")
            
        functions = {
            fid: LambdaFunction(id=fid, name=props.get('name', fid), memory=props.get('mem', 256), baseline_runtime=props.get('rt', 100))
            for fid, props in functions_spec.items()
        }
        
        for fid, props in functions_spec.items():
            if 'children' in props and fid in functions:
                for child_id, data_bytes in props['children'].items():
                    if child_id in functions:
                        functions[fid].add_child(functions[child_id], data_bytes)
        
        return Application(
            name=repo_name,
            functions=list(functions.values()),
            critical_path_ids=spec.get('critical_path', []),
            max_memory=constraints_spec.get('max_memory', 1024),
            max_latency=constraints_spec.get('max_latency', 1000),
            network_hop_delay=constraints_spec.get('network_delay', 10)
        )

    @staticmethod
    def enrich_with_live_data(app: Application, live_metrics: Dict[str, Any]) -> Application:
        """
        Updates an existing Application object with live performance metrics from AWS.
        """

        func_name_map = {func.name: func for func in app.functions}

        for func_name_from_aws, metrics in live_metrics.items():

            if func_name_from_aws in func_name_map:
                target_func = func_name_map[func_name_from_aws]

                target_func.baseline_runtime = metrics.get('avg_runtime_ms', target_func.baseline_runtime)
                target_func.memory = metrics.get('avg_memory_mb', target_func.memory)
        
        return app