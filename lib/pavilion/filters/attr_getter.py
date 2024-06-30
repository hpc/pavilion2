from datetime import datetime
from functools import wraps
from typing import Dict, Union, Any, Hashable, Callable, Mapping

from pavilion.test_run import TestAttributes
from pavilion.series import SeriesInfo

from .common import identity


Transform = Callable[[Any], Any]
TransformMap = Mapping[Hashable, Transform] 
GetterMethod = Callable[[object, Hashable, Any], Any]


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


class AttributeGetter:
    """Provides a common interface for accessing attributes on TestAttributes
    and SeriesInfo objects, as well as dicts, which serve as mocks for testing."""

    SERIES_KEYS = {'complete', 'name', 'user', 'sys_name', 'created', 'finished', 'all_started', 'state_history'}
    TEST_KEYS = {'created', 'finished', 'result', 'sys_name', 'user', 'partition', 'node_list', 'result', 'complete', 'state', 'name', 'sys_name', 'state_history'}
    COMMON_KEYS = SERIES_KEYS & TEST_KEYS
    ALL_KEYS = SERIES_KEYS | TEST_KEYS

    GETTERS = {
        'state_history': lambda x: x._get_status_file().history()
    }

    KEY_TRANSFORMS = {
        'created': lambda x: x if isinstance(x, datetime) else datetime.fromtimestamp(x),
    }

    def __init__(self, attrs: Union[TestAttributes, SeriesInfo, Dict]):
        self.target = attrs

    @transform_getter(KEY_TRANSFORMS)
    def get(self, key: Hashable, default: Any = None) -> Any:
        if self._validate_key(key):
            getter = self.GETTERS.get(key, lambda x: x.get(key))

            return getter(self.target)

        return default

    def __get__(self, key: Hashable) -> Any:
        return self.get(key)
        
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


