from ..core import CompositeFunction

def _get_func_to_group_map(groups: list[CompositeFunction]) -> dict[
    str, CompositeFunction]:
    """Maps each atomic function ID to its parent composite group."""
    func_map = {}
    for group in groups:
        for func in group.member_functions:
            func_map[func.id] = group
    return func_map