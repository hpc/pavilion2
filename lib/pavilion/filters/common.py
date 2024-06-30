"""Miscellaneous functions for use with filters."""

from datetime import datetime
from typing import Any, Callable, TypeVar, Union


T = TypeVar('T')

def identity(x: T) -> T:
    """The identity function. Returns its input unchanged."""

    return x

def const(x: T) -> Callable[[Any], T]:
    """Creates a constant function, which returns x
    regardless of the input."""

    def f(_: Any) -> T:
        return x

    return f
