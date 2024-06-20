from pathlib import Path
from enum import Enum, auto
from itertools import starmap
from fnmatch import fnmatchcase
from datetime import datetime
from typing import List, Dict, Union, Optional, Any, Callable

from pavilion.test_run import TestRun, TestAttributes
from pavilion.status_file import TestStatusFile, SeriesStatusFile
from pavilion.series import SeriesInfoBase, SeriesInfo, get_all_started, STATUS_FN
from pavilion.variables import VariableSetManager


class TargetType(Enum):
    TEST = auto()
    SERIES = auto()


def get_node_list(info: Union[Dict, SeriesInfoBase]) -> Optional[List[str]]:
   info = MonadicDict(info)

   return info.get('results').get('sched').get('test_node_list').resolve()


# These functions tell the aggregator how to get or compute the various
# properties relevant to filtering
INFO_KEYS = {
    'complete': lambda x: x.get('complete', False),
    'name': lambda x: x.get('name'),
    'user': lambda x: x.get('user'),
    'sys_name': lambda x: x.get('sys_name'),
    'result': lambda x: x.get('result'),
    'created': lambda x: datetime.fromtimestamp(x.get('created')),
    'partition': lambda x: x.get('partition'),
    'finished': lambda x: x.get('finished'),
    'node_list': get_node_list,
    'all_started': lambda x: get_all_started(Path(x.get('path')))
    }


# Additonal test attributes to be defined on the StateAggregate
# object, and their associated defaul values
ADDITIONAL_ATTRS = {
    'path': None,
    'type': None,
    'state': None,
    'state_history': [],
}
    

class MonadicDict:
    """Utility class for getting values from a nested dict. This
    prevents having to repeatedly check whether each key exists
    in the underlying dictionary."""

    def __init__(self, mdict: Any, default: Any = None):
        self.value = mdict
        self.default = default

    def get(self, key: Any) -> 'MonadicDict':
        if isinstance(self.value, dict):
            return MonadicDict(self.value.get(key, self.default))

        # Note: this could cause some unexpected behavior when
        # assigning new values, but deep copying and creating
        # a new MonadicDict is potentially expensive
        return self

    def resolve(self) -> Any:
        return self.value


class StateAggregate:
    """Lightweight object containing all information relevant to test
    and series filters."""

    def __init__(self):
        for attr, default in ADDITIONAL_ATTRS.items():
            self.__dict__[attr] = default

        for attr in INFO_KEYS:
            self.__dict__[attr] = None
    
    def num_nodes(self) -> int:
        if self.node_list is None:
            return 0

        return len(self.node_list)

    def name_matches(self, name_glob: str) -> bool:
        name_comps = self.get('name', '').split('.')
        glob_comps = name_glob.split('.')

        matches = starmap(fnmatchcase, zip(name_comps, glob_comps))

        return all(matches)

    def user_matches(self, user_glob: str) -> bool:
        return self.user is not None and fnmatchcase(self.user, user_glob)

    def sys_name_matches(self, sys_name: str) -> bool:
        return self.user is not None and self.sys_name == sys_name

    def nodes_match(self, node_glob: str) -> bool:
        matches = map(lambda x: fnmatchcase(x, node_glob), self.node_list)

        return any(matches)

    @property
    def passed(self) -> bool:
        return self.result is not None and self.result == TestRun.PASS

    @property
    def failed(self) -> bool:
        return self.result is not None and self.result == TestRun.FAIL

    def has_error(self) -> bool:
        return self.result is not None and self.result == TestRun.ERROR

    def has_state(self, state: str) -> bool:
        return state in map(lambda x: x.state, self.state_history)

    @staticmethod
    def from_dict(state_dict: Dict) -> 'StateAggregate':
        agg = StateAggregate()

        for k, v in state_dict.items():
            setattr(agg, k, v)

        return agg

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, item: Any) -> bool:
        return item in INFO_KEYS or item in ADDITIONAL_ATTRS

class FilterAggregator:
    def __init__(self, attrs: TestAttributes, info: SeriesInfoBase, status_file: TestStatusFile,
                    target_type: TargetType):
            self.attrs = attrs
            self.info = info
            self.status_file = status_file
            self.type = target_type
            self.path = Path(self.info.get("path"))

    def _load_node_list(self) -> Optional[List[str]]:
        var_path = self.path / 'variables'

        if var_path.exists():
            var_dict = VariableSetManager.load(self.path / 'variables')
            var_dict = MonadicDict(vars.as_dict())

            return var_dict.get('sched').get('test_node_list').resolve()

        return None

    def aggregate(self) -> StateAggregate:
        """Aggregate all information relevant to filters from disparate
        state objects."""

        agg = StateAggregate()

        setattr(agg, 'path', self.path)
        setattr(agg, 'type', self.type)

        for key, func in INFO_KEYS.items():
            setattr(agg, key, func(self.info))

        setattr(agg, 'state', self.status_file.current().state)
        setattr(agg, 'state_history', self.status_file.history())

        if agg.node_list is None:
            setattr(agg, 'node_list', self._load_node_list())

        return agg


def aggregate_transform(path: Path, status_class: TestStatusFile) -> StateAggregate:
    """Transform the given path into a StateAggregate object. Intended to be
    passed as a transform to dir_db functions (partially applied to the
    appropriate target type)."""

    attrs = TestAttributes(path)
    status_file = status_class(path)

    agg = FilterAggregator(attrs, status_file, VariableSetManager)

    return agg.aggregate()


def make_aggregate_transform(target_type: TargetType) -> Callable[[Path], StateAggregate]:
    if target_type == TargetType.TEST:
       status_file = TestStatusFile 
    else:
        status_file = SeriesStatusFile

    def path_to_aggregate(path: Path) -> StateAggregate:
        return aggregate_transform(path, status_file)

    return path_to_aggregate
