from typing import List, Union, TypeVar, Iterator, Iterable, Callable, Optional

T = TypeVar("T")


def enforce_list(val: Union[T, List[T]]) -> List[T]:
    if isinstance(val, list):
        return val

    return list(val)

def replace(lst: Iterable[T], old: T, new: T) -> Iterator[T]:
    return map(lambda x: new if x == old else x, lst)

def remove_none(lst: Iterable[T]) -> Iterator[T]:
    return filter(lambda x: x is not None, lst)

def first(pred: Callable[[T], bool], lst: Iterable[T]) -> Optional[T]:
    filtered = list(filter(pred, lst))

    if len(filtered) > 0:
        return filtered[0]

    return None
