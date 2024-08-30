"""Simple utilities for dealing with paths."""

from pathlib import Path
from typing import Union, Callable

Pathlike = Union[Path, str]

def exists(path: Path) -> bool:
    """Wraps Path.exists, which obviates the need for
    a lambda function when mapping it."""

    return path.exists()

def append_path(suffix: Pathlike) -> Callable[[Path], Path]:
    """Constructs a function that appends the given suffix
    to a path. Intended for use with map."""

    def f(path: Path) -> Path:
        return path / suffix

    return f

def shortpath(path: Path, parents: int = 1) -> Path:
    """Return an abbreviated version of a path, where only
    the specified number of parents are included."""

    return Path(*path.parts[-(1 + parents):])
