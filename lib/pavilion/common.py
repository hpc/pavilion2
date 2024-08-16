from typing import TypeVar, Optional

T = TypeVar("T")

def set_default(val: Optional[T], default: T) -> T:
    """Set the input value to its default, if it is None."""

    if val is None:
        return default

    return val

def get_nested(keys: Iterable[Hashable], dict: Dict) -> Dict:
    """Safely get the hierarchical sequence of keys off the
    dictionary. Guaranteed to return a dictionary."""
