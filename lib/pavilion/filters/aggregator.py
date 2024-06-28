from pathlib import Path
from itertools import starmap
from fnmatch import fnmatchcase
from datetime import datetime
from collections import defaultdict
from operator import attrgetter
from typing import List, Dict, Union, Optional, Any, Callable, Hashable

from pavilion.test_run import TestRun, TestAttributes
from pavilion.status_file import TestStatusFile, SeriesStatusFile
from pavilion.series import SeriesInfo, get_all_started, STATUS_FN
from pavilion.variables import VariableSetManager

from .transform_mapping import transform


class AttributeGetter:
    """Provides a common interface for accessing attributes on TestAttributes
    and SeriesInfo objects, as well as dicts, which serve as mocks for testing."""

    SERIES_KEYS = {'complete', 'name', 'user', 'sys_name', 'created', 'finished', 'all_started', 'state_history'}
    TEST_KEYS = {'created', 'finished', 'result', 'sys_name', 'user', 'partition', 'node_list', 'result', 'complete', 'state', 'name', 'sys_name', 'state_history'}
    COMMON_KEYS = SERIES_KEYS & TEST_KEYS
    ALL_KEYS = SERIES_KEYS | TEST_KEYS

    GETTERS = {
        'state_history': lambda x: x.status.history()
    }

    KEY_TRANSFORMS = {
        'created': lambda x: x if isinstance(x, datetime) else datetime.fromtimestamp(x),
    }

    def __init__(self, attrs: Union[TestAttributes, SeriesInfo, Dict]):
        self.target = attrs

    @transform(KEY_TRANSFORMS)
    def get(self, key: Hashable) -> Any:
        if self._validate_key(key):
            getter = self.GETTERS.get(key, lambda x: x.get(key))

            return getter(self.target)
        else:
            raise KeyError(f"Invalid key {key} for AttributeGetter[{type(self.target)}].")

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
