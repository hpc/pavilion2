from pathlib import Path
from enum import Enum, auto
import fnmatch
import re
from typing import List, Dict, Union, Optional, Any

from pavilion.test_run import TestRun, TestAttributes
from pavilion.status_file import TestStatusFile, SeriesStatusFile
from pavilion.series import SeriesInfo, get_all_started
from pavilion.variables import VariableSetManager


class TargetType(Enum):
    TEST = auto()
    SERIES = auto()


def get_node_list(info: Union[Dict, SeriesInfo]) -> Optional[List[str]]:
   info = MaybeDict(info)

   return info.get('results').get('sched').get('test_node_list').resolve()


# These functions tell the aggregator how to get or compute the various
# properties relevant to filtering
INFO_KEYS = {
    'complete': lambda x: x.get('complete', False),
    'name': lambda x: x.get('name'),
    'user': lambda x: x.get('user'),
    'sys_name': lambda x: x.get('sys_name'),
    'result': lambda x: x.get('result'),
    'created': lambda x: x.get('created'),
    'partition': lambda x: x.get('partition'),
    'finished': lambda x: x.get('finished'),
    'node_list': get_node_list,
    'all_started': lambda x: get_all_started(Path(x.get('path')))
    }
    

class MaybeDict:
    """Utility class for getting values from a nested dict. This
    prevents having to repeatedly check whether each key exists
    in the underlying dictionary."""

    def __init__(self, mdict: Any, default: Any = None):
        self.value = mdict
        self.default = default

    def get(self, key) -> 'MaybeDict':
        if isinstance(self.value, dict):
            return MaybeDict(self.value.get(key, self.default))

        # Note: this could cause some unexpected behavior when
        # assigning new values, but deep copying and creating
        # a new MaybeDict is potentially expensive
        return self

    def resolve(self) -> Any:
        return self.value


class StateAggregate:
    """Lightweight object containing all information relevant to test
    and series filters."""

    def __init__(self):
        self.path = None
        self.type = None
        self.state = None
        self.state_history = None

        for attr in INFO_KEYS:
            self.__dict__[attr] = None
    
    def num_nodes(self) -> int:
        if self.node_list is None:
            return 0

        return len(self.node_list)

    def name_matches(self, name: str) -> bool:
        name_parse = re.compile(r'^([a-zA-Z0-9_*?\[\]-]+)'  # The test suite name.
                                r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?'  # The test name.
                                r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?$'  # The permutation name.
                                )
        test_name = attrs.get('name') or ''
        filter_match = name_parse.match(name)
        name_match = name_parse.match(test_name)

        if filter_match is not None:
            suite, test, perm = tuple(map(lambda x: '*' if x is None else x, filter_match.groups()))

        if name_match is not None:
            _, _, test_perm = name_match.groups()

            # allows permutation glob filters to match tests without permutations
            # e.g., name=suite.test.* will match suite.test
            if test_perm is not None:
                test_name = test_name + '.*'

        new_val = '.'.join([suite, test, perm])

        return fnmatch.fnmatch(test_name, new_val)

    def user_matches(self, user: str) -> bool:
        if self.user is None:
            return False

        return self.user == user

    def sys_name_matches(self, sys_name: str) -> bool:
        if self.sys_name is None:
            return False

        return self.sys_name == sys_name

    def nodes_match(self, node_range: str) -> bool:
        for node in self.node_list:
            if not fnmatch.fnmatch(node, node_range):
                return False

        return True

    def passed(self) -> bool:
        if self.result is None:
            return False
        
        return self.result == TestRun.PASS

    def failed(self) -> bool:
        if self.result is None:
            return False

        return self.result == TestRun.FAIL

    def has_error(self) -> bool:
        if self.result is None:
            return False

        return self.result == TestRun.ERROR


class FilterAggregator:
    def __init__(self, attrs: TestAttributes, info: SeriesInfo, status_file: TestStatusFile,
                    target_type: TargetType):
            self.attrs = attrs
            self.info = info
            self.status_file = status_file
            self.type = target_type
            self.path = Path(self.info.get('path'))

    def _load_node_list(self) -> Optional[List[str]]:
        var_path = self.path / 'variables'

        if var_path.exists():
            var_dict = VariableSetManager.load(self.path / 'variables')
            var_dict = MaybeDict(vars.as_dict())

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


def aggregate_transform(path: Path, target_type: TargetType) -> StateAggregate:
    """Transform the given path into a StateAggregate object. Intended to be
    passed as a transform to dir_db functions (partially applied to the
    appropriate target type)."""

    attrs = TestAttributes(path)
    info = SeriesInfo(..., path)

    if target_type == TargetType.TEST:
        status_file = TestStatusFile(path)
    else:
        status_file = SeriesStatusFile(path)

    agg = FilterAggregator(attrs, info, status_file, VariableSetManager)

    return agg.aggregate()
