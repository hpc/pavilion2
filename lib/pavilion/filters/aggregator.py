from pathlib import path
from enum import Enum, Auto
from typing import List, Dict, Union, Optional, Any

from pavilion.test_run import TestRun
from pavilion.status_file import TestStatusFile, SeriesStatusFile
from pavilion.series import SeriesInfo

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
    'node_list': get_node_list
    }


class TargetType(Enum):
    TEST = auto()
    SERIES = auto()


class MaybeDict:
    """Utility class for getting values from a nested dict. This
    prevents having to repeatedly check whether each key exists
    in the underlying dictionary."""

    def __init__(self, mdict: Any):
        self.value = mdict

    def get(self, key) -> 'MaybeDict':
        if isinstance(self.value, mdict):
            return MaybeDict(self.value.get())

        return self

    def resolve(self) -> Any:
        return self.value


def get_node_list(info: Union[Dict, SeriesInfo]) -> Optional[List[str]]:
   info = MaybeDict(info)

   return info.get('results').get('sched').get('test_node_list').resolve()


class StateAggregate:
    """Lightweight object containing all information relevant to test
    and series filters."""
    
    def is_test(self) -> bool:
        return self.type == TEST

    def is_series(self) -> bool:
        return self.test == SERIES

    def num_nodes(self) -> int:
        if self.node_list is None:
            return 0

        return len(self.node_list)

    def name_matches(self) -> bool:
        ...

    def user_matches(self) -> bool:
        ...

    def sys_name_matches(self, sys_name: str) -> bool:
        ...

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
    def __init__(self, path: Path, target_type: TargetType):
        self.path = path
        self.type = target_type

        self.attrs = TestAttributes(path, load=False)
        self.info = SeriesInfo(..., path) # TODO: figure out what needs to be passed in as pav_cfg

        if target_type == TargetType.TEST
            self.status_file = TestStatusFile(path)
        else
            self.status_file = SeriesStatusFile(path)

    def _load_node_list(self) -> Optional[List[str]]:
        var_dict = variables.VariableSetManager.load(self.path / 'variables')
        var_dict = MaybeDict(vars.as_dict())

        return var_dict.get('sched').get('test_node_list').resolve()

    def aggregate(self) -> StateAggregate:
        """Aggregate all information relevant to filters from disparate
        state objects."""

        agg = StateAggregate()

        setattr(agg, 'path', self.path)
        setattr(agg, 'type', self.type)

        for key, func in INFO_KEYS:
            setattr(agg, key, func(self.info))

        setattr(agg, 'state', self.status_file.current().state)
        setattr(agg, 'state_history', self.status_file.history())

        if agg.node_list is None:
            setattr(agg, 'node_list', self._load_node_list())

        return agg
