# Will contain ApplicationBuilder
from dataclasses import dataclass
from ..core import LambdaFunction

@dataclass
class Application:
    """Encapsulates a serverless application's structure and constraints."""
    name: str
    functions: list[LambdaFunction]
    critical_path_ids: list[str]
    max_memory: int
    max_latency: int
    network_hop_delay: int = 10

    @property
    def functions_map(self) -> dict[str, LambdaFunction]:
        return {f.id: f for f in self.functions}

    @property
    def root_function(self) -> LambdaFunction:
        return next(f for f in self.functions if f.parent is None)

    @property
    def critical_path_functions(self) -> list[LambdaFunction]:
        return [self.functions_map[fid] for fid in self.critical_path_ids]