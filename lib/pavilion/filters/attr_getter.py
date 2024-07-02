from datetime import datetime
from functools import wraps
from numbers import Number
from typing import (Dict, Union, Any, Hashable, Callable, Mapping, Iterator,
    Tuple, Optional, List)

from pavilion.test_run import TestAttributes
from pavilion.series import SeriesInfo

from .common import identity


Transform = Callable[[Any], Any]
TransformMap = Mapping[Hashable, Transform] 
GetterMethod = Callable[[object, Hashable, Any], Any]
Filterable = Union[TestAttributes, SeriesInfo, Dict]


def transform_getter(transforms: TransformMap, 
              default_transform: Transform = identity) -> Callable[[GetterMethod], GetterMethod]:
    """Given a transform map, returns a decorator for a getter method which first calls
    the getter method with the provided key, then applies to the returned value the
    transfrom associated in the map with the same key. For example, if the wrapped getter
    method encodes the following mapping:

    'foo' -> 7

    and the transform map contains:

    'foo' -> lambda x: x*x

    then the wrapped method will return 49 when called with the key 'foo'.

    """

    def f(func: GetterMethod) -> GetterMethod:
    
        @wraps(func)
        def get_and_transform(self: object, key: Hashable, **kwargs) -> Any:
            tform = transforms.get(key, default_transform)
            
            return tform(func(self, key, **kwargs))

        return get_and_transform

    return f


def get_history(target: Filterable) -> Optional[List]:
    if isinstance(target, dict):
        return target.get('state_history')

    status_file = target._get_status_file()

    if status_file is None:
        return None

    return status_file.history()


def transform_created(created: Union[int, datetime]) -> Optional[datetime]:
    if isinstance(created, (int, float)):
        return datetime.fromtimestamp(created)

    return created


class AttributeGetter:
    """Provides a common interface for accessing attributes on TestAttributes
    and SeriesInfo objects, as well as dicts, which serve as mocks for testing."""

    SERIES_KEYS = {'complete', 'name', 'user', 'sys_name', 'created', 'finished', 'all_started', 'state_history'} | set(SeriesInfo.list_attrs())
    # TODO: Implement 'partition' and 'node_list' keys
    TEST_KEYS = {'created', 'finished', 'result', 'sys_name', 'user', 'result', 'complete', 'state', 'name', 'sys_name', 'state_history'} | set(TestAttributes.list_attrs())
    COMMON_KEYS = SERIES_KEYS & TEST_KEYS
    ALL_KEYS = SERIES_KEYS | TEST_KEYS

    GETTERS = {
        'state_history': get_history
    }

    KEY_TRANSFORMS = {
        'created': transform_created
    }

    def __init__(self, attrs: Filterable):
        self.target = attrs

    def get(self, key: Hashable, default: Any = None) -> Any:
        if self._validate_key(key):
            return self._get(key, default=default)

        return default

    @transform_getter(KEY_TRANSFORMS)
    def _get(self, key: Hashable, default: Any = None):
        """Unvalidated variant of get."""

        getter = self.GETTERS.get(key, lambda x: x.get(key))

        return getter(self.target)

    def _validate_key(self, key: Hashable) -> bool:
        if key in self.COMMON_KEYS:
            return True
        if isinstance(self.target, TestAttributes):
            return key in self.TEST_KEYS
        if isinstance(self.target, SeriesInfo):
            return key in self.SERIES_KEYS
        if isinstance(self.target, dict):
            return key in self.ALL_KEYS

        raise ValueError(f"Unsupported type {type(target)} for AttributeError")

    def items(self) -> Iterator[Tuple[Hashable, Any]]:
        if isinstance(self.target, TestAttributes):
            keys = self.TEST_KEYS
        elif isinstance(self.target, SeriesInfo):
            keys = self.SERIES_KEYS
        else:
            keys = self.ALL_KEYS

        return ((key, self._get(key)) for key in keys)

    def __getitem__(self, key: Hashable) -> Any:
        return self.get(key)

    def __delitem__(self, key: Hashable) -> None:
        pass

    def __eq__(self, other: "AttributeGetter") -> bool:
        # Convert to sets, since order of items is indeterminate
        return set(self.items()) == set(other.items())
