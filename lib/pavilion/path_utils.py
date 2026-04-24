"""Simple utilities for dealing with paths."""

from pathlib import Path
from operator import truediv
from itertools import starmap, product
from typing import Union, Callable, Iterable, Iterator

Pathlike = Union[Path, str]

def exists(path: Path) -> bool:
    """Wraps Path.exists, which obviates the need for
    a lambda function when mapping it."""

    return path.exists()

def is_dir(path: Path) -> bool:
    """Wraps Path.id_dir, which obviates the need for
    a lambda function when mapping it."""

    return path.id_dir()

def append_file(path: Path) -> Callable[[Pathlike], Path]:
    """Constructs a function that takes a file name and appends
    it to a constant path. Intended for use with map."""

    def func(fname: Pathlike) -> Path:
        return path / fname

    return func

def append_const_file(fname: Pathlike) -> Callable[[Path], Path]:
    """Constructs a function that takes a path and appends a
    constant file name to it. Intended for use with map."""

    def func(path: Path) -> Path:
        return path / fname

    return func

def shortpath(path: Path, parents: int = 1) -> Path:
    """Return an abbreviated version of a path, where only
    the specified number of parents are included."""

    return Path(*path.parts[-(1 + parents):])

def path_product(roots: Iterable[Path], stems: Iterable[Pathlike]) -> Iterator[Path]:
    """Given a list of root paths and a list of stem paths, returns an iterator
    over all paths formed by the Cartesian products of those lists."""

    return starmap(truediv, product(roots, stems))

def is_empty(dir: Pathlike) -> bool:
    """Determines whether the given directory is empty."""

    return not any(Path(dir).iterdir())
