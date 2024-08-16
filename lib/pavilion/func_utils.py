"""A collection of utilities defined using functional methods"""

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
    return filter(lambda x: x is not None, lst)

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
    for key in keys:
        nested_dict = nested_dict.get(key, {})

    return nested_dict
