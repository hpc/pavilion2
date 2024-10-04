"""A collection of 'microfunctions' primarily designed to abstract common
tasks and patterns, for the purpose of conciseness and readability."""

from pathlib import Path
from itertools import filterfalse, chain, tee
from typing import (List, Union, TypeVar, Iterator, Iterable, Callable, Optional,
                    Hashable, Dict, Tuple)

T = TypeVar('T')
U = TypeVar('U')


def partition(pred: Callable[[T], bool], lst: Iterable[T]) -> Tuple[Iterator[T], Iterator[T]]:
    """Partition the sequence into two sequences: one consisting of the elements
    for which the given predicate is true and one consisting of those for
    which it is false."""

    f_true, f_false = tee(lst)

    return filter(pred, f_true), filterfalse(pred, f_false)

def flatten(lst: Iterable[Iterable[T]]) -> Iterator[T]:
    """Convert a singly nested iterable into an unnested iterable."""
    return chain.from_iterable(lst)

def remove_all(lst: Iterable[T], item: T) -> Iterator[T]:
    """Remove all instances of the given item from the iterable."""
    return filter(lambda x: x != item, lst)

def unique(lst: Iterable[T]) -> List[T]:
    """Return a list of the unique items in the original list."""
    return list(set(lst))

def replace(lst: Iterable[T], old: T, new: T) -> Iterator[T]:
    """Replace all instances of old with new."""
    return map(lambda x: new if x == old else x, lst)

def remove_none(lst: Iterable[T]) -> Iterator[T]:
    """Remove all instances of None from the iterable."""
    return remove_all(lst, None)

def first(pred: Callable[[T], bool], lst: Iterable[T]) -> Optional[T]:
    """Return the first item of the list that satisfies the given
    predicate, or None if no item does."""

    for item in filter(pred, lst):
        return item

def apply_to_first(func: Callable[[T], U], pred: Callable[[T], bool],
                    lst: Iterable[T]) -> Optional[U]:
    """Apply the function to the first element of the list that satisfies
    the given predicate. If no element satisfies the predicate, return None."""

    fst = first(pred, lst)

    if fst is not None:
        return func(fst)

def get_nested(keys: Iterable[Hashable], nested_dict: Dict) -> Dict:
    """Gets the values associated with the given sequence of keys
    out of a nested dictionary. If any key in the sequence does
    not exist during the process, returns an empty dictionary."""

    for key in keys:
        nested_dict = nested_dict.get(key, {})

    return nested_dict

def listmap(func: Callable[[T], U], lst: Iterable[T]) -> List[U]:
    """Map a function over an iterable, but return a list instead
    of a map object."""
    return list(map(func, lst))

def set_default(val: Optional[T], default: T) -> T:
    """Set the input value to default, if the original value is None.
    Otherwise, return the value unchanged."""

    if val is None:
        return default

    return val
