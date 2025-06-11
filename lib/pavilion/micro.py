"""
A collection of 'microfunctions' primarily designed to abstract common
tasks and patterns, for the purpose of conciseness and readability.

Some functions are borrowed from the recipes in the itertools docs:

https://docs.python.org/3/library/itertools.html#itertools-recipes
"""

from pathlib import Path
from itertools import filterfalse, chain, tee, islice, starmap
from collections import deque
from typing import (List, Union, TypeVar, Iterator, Iterable, Callable, Optional, Hashable, Dict,
                    Tuple, Any, Type)

T = TypeVar('T')
U = TypeVar('U')


def partition(pred: Callable[[T], bool], lst: Iterable[T]) -> Tuple[Iterator[T], Iterator[T]]:
    """Partition the sequence into two sequences: one consisting of the elements
    for which the given predicate is true and one consisting of those for
    which it is false."""

    f_true, f_false = tee(lst)

    return filter(pred, f_true), filterfalse(pred, f_false)

def flatten(lst: Iterable[Iterable[T]]) -> Iterator[T]:
    """Convert a singly nested iterable into an unnested iterable.

    Borrowed from the itertools docs."""
    return chain.from_iterable(lst)

def remove_all(lst: Iterable[T], item: T) -> Iterator[T]:
    """Remove all instances of the given item from the iterable."""
    return filter(lambda x: x != item, lst)

def unique(lst: Iterable[T]) -> List[T]:
    """Return a list of the unique items in the original list.
    Not guaranteed to preserve the order of unique items."""
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

    return next(filter(pred, lst), None)

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

def listfilter(pred: Callable[[T], bool], lst: Iterable[T]) -> List[T]:
    """Filter an iterable by the given predicate, returning a list
    rather than an iterator."""
    return list(filter(pred, lst))

def set_default(val: Optional[T], default: T) -> T:
    """Set the input value to default, if the original value is None.
    Otherwise, return the value unchanged."""

    if val is None:
        return default

    return val

def consume(lst: Iterator[Any], num_items: int = None) -> None:
    """Advance the iterator by num_items. If n is None, consume entirely.

    Useful for forcing side-effects for mapped functions."""

    if num_items is None:
        deque(lst, maxlen=0)
    else:
        next(islice(lst, num_items, num_items), None)

# pylint: disable=C0103
def do(func: Callable[[T], Any], lst: Iterable[T]) -> None:
    """Map the function over the sequence of objects, ensuring
    that all side effects occur. This is necessary because map
    is lazily evaluated."""

    consume(map(func, lst))

def stardo(func: Callable, lst: Iterable) -> None:
    """Analogue of do using starmap."""

    consume(starmap(func, lst))

def promote(item: Union[T, Type[T]], ptype: Type) -> Type[T]:
    """Promote the item to the type ptype, if it is not already of that type."""

    if isinstance(item, ptype):
        return item

    return ptype(item)
