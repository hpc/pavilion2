from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Dict, Union, List

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile, TestStatusInfo

from .aggregator import StateAggregate
from .validators import (validate_int, validate_glob, validate_glob_list, validate_str_list,
    validate_datetime, validate_str, validate_name_glob)
from .errors import FilterParseError

from lark import Transformer, Discard, Token


MICROSECS_PER_SEC = 10**6

SPECIAL_FUNCS = {
    'RESULT_ERROR': lambda x: x.has_error()
}


class FilterTransformer(Transformer):

    def __init__(self, agg: Union[StateAggregate, Dict]):
        super().__init__()
        self.aggregate = agg

    def or_expr(self, expr: List[Any]) -> bool:
        if len(expr) == 1:
            return expr[0]

        return expr[0] or expr[2]

    def and_expr(self, expr: List[Any]) -> bool:
        if len(expr) == 1:
            return expr[0]

        return expr[0] and expr[2]

    def not_expr(self, expr: List[Any]) -> bool:
        if len(expr) == 1:
            return expr[0]

        return not expr[1]

    def comp_expr(self, expr: List[Any]) -> bool:
        func_name, operator, rval = tuple(expr)

        return getattr(self, func_name)(operator, rval)

    def special(self, special: List[Token]) -> bool:
        name = str(special[0])
        func = SPECIAL_FUNCS.get(name, lambda x: getattr(x, name))

        return func(self.aggregate)

    def keyword(self, kw: List[Token]) -> str:
        return f"_{str(kw[0]).lower()}"

    def duration(self, duration: List[Token]) -> datetime:
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        datetime.now() - timedelta(**{unit: num})
    
    def partial_iso_date(self, iso: List[Token]) -> date:
        iso = tuple(map(int, iso))

        month = 1
        day = 1

        year = iso[0]
        
        if len(iso) > 1:
            month = iso[1]
        if len(iso) > 2:
            day = iso[2] 

        return date(year, month, day)

    def partial_iso_time(self, iso: List[Token]) -> time:
        if len(iso) == 3:
            hrs, mins, secs = tuple(iso)
            microsecs = (float(secs) - int(secs)) * MICROSECS_PER_SEC
            iso.append(microsecs)

        iso = tuple(map(int, iso))

        return time(*iso)

    def partial_iso(self, iso: List[Union[date, time]]) -> Union[date, time, datetime]:
        if len(iso) == 2:
            return datetime.combine(iso[0], iso[1])

        return iso[0]

    def GLOB(self, glob: Token) -> str:
        return str(glob)

    def NUMBER(self, num: Token) -> float:
        return float(num)

    def INT(self, num: Token) -> int:
        return int(num)

    def WS(self, ws) -> Discard:
        return Discard

    def LT(self, _) -> str:
        return "<"

    def GT(self, _) -> str:
        return ">"

    def LT_EQ(self, _) -> str:
        return "<="

    def GT_EQ(self, _) -> str:
        return ">="

    def EQ(self, _) -> str:
        return  "="

    def NOT_EQ(self, _) -> str:
        return "!="

    @validate_int
    def _num_nodes(self) -> int:
        return self.aggregate.num_nodes

    @validate_name_glob
    def _name(self) -> str:
        return self.aggregate.get("name")

    @validate_glob
    def _user(self) -> str:
        return self.aggregate.get("user")

    @validate_glob
    def _sys_name(self) -> str:
        return self.aggregate.get("sys_name")

    @validate_glob_list
    def _nodes(self) -> List[str]:
        return self.aggregate.get("nodes")

    @validate_str_list
    def _has_state(self) -> List[TestStatusInfo]:
        return map(lambda x: x.state, self.aggregate.get("state_history"))

    @validate_datetime
    def _created(self) -> datetime:
        return self.aggregate.get("created")

    @validate_str
    def _state(self) -> str:
        return self.aggregate.get("state")
