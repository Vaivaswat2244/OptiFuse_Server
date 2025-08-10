# Will contain LambdaFunction, CompositeFunction, Application classes
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LambdaFunction:
    """Represents a serverless function with its properties, now including load."""
    id: str
    name: str
    memory: int
    baseline_runtime: int
    load_factor: float = 1.0
    data_out_edges: dict[str, int] = field(default_factory=dict)
    parent: Optional['LambdaFunction'] = None
    children: list['LambdaFunction'] = field(default_factory=list)

    @property
    def runtime(self) -> int:
        """The actual runtime, adjusted for the current load factor."""
        return int(self.baseline_runtime * self.load_factor)

    def add_child(self, child: 'LambdaFunction', data_bytes: int = 0):
        self.children.append(child)
        child.parent = self
        self.data_out_edges[child.id] = data_bytes

    def get_data_transfer_cost(self, child_id: str) -> float:
        bytes_transferred = self.data_out_edges.get(child_id, 0)

        return (bytes_transferred / (1024 * 1024 * 1024)) * 0.01

    def get_execution_cost(self) -> float:
        """Execution cost is now based on the load-adjusted runtime."""
        gb_seconds = (self.memory / 1024) * (self.runtime / 1000)
        return 0.00001667 * gb_seconds

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, LambdaFunction) and self.id == other.id

    def __repr__(self):
        return f"LambdaFunction(id='{self.id}')"

@dataclass
class CompositeFunction:
    """
    Represents a fused group of functions, treated as a single deployable unit.
    The internal sequence of member functions is preserved.
    """
    member_functions: list[LambdaFunction]

    @property
    def id(self) -> str:
        return self.member_functions[0].id

    @property
    def memory(self) -> int:
        """Total memory is the sum of memories of all member functions."""
        return sum(f.memory for f in self.member_functions)

    @property
    def runtime(self) -> int:
        """Total runtime is the sum of runtimes of all members, executed sequentially."""
        return sum(f.runtime for f in self.member_functions)

    def get_execution_cost(self) -> float:
        """
        Calculates the cost for a SINGLE invocation of this composite function,
        billed for its total runtime and total memory.
        """
        gb_seconds = (self.memory / 1024) * (self.runtime / 1000)
        return 0.00001667 * gb_seconds