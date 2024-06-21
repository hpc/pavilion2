from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Dict, Union, List

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile, TestStatusInfo

from .aggregator import StateAggregate
from .validators import (validate_int, validate_glob, validate_glob_list, validate_str_list,
    validate_datetime, validate_str, validate_name_glob)
from .errors import FilterParseError

from lark import Transformer, Discard, Token


MICROSECS_PER_SEC = 10**6


def comp_str_to_symbol(comp_str: str) -> str:
    """Convert an alphabetic name for a comparator into the corresponding symbol."""

    if comp_str == 'eq':
        return '='
    if comp_str == 'neq':
        return '!='
    if comp_str == 'lt':
        return '<'
    if comp_str == 'gt':
        return '>'
    if comp_str == 'lte':
        return '<='
    if comp_str == 'gte':
        return '>='


class FilterTransformer(Transformer):

    def __init__(self, agg: Union[StateAggregate, Dict]):
        super().__init__()
        self.aggregate = agg
    
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

    def INT(self, INT: Token) -> int:
        return int(INT)

    def WS(self, ws) -> Discard:
        return Discard

    def duration(self, duration: List[Token]) -> datetime:
        duration = tuple(duration)
        num, unit = duration
        num = int(num)
        unit = str(unit.data) + 's'

        datetime.now() - timedelta(**{unit: num})

    def unary_expression(self, exp: List) -> bool:
        return not exp[1]

    def binary_expression(self, exp: List) -> bool:
        operand1, connective, operand2 = tuple(exp)

        if connective == f_and:
            return operand1 and operand2
        elif connective == f_or:
            return operand1 or operand2

    def passed(self, _) -> bool:
        return self.aggregate.get("passed")

    def failed(self, _) -> bool:
        return self.aggregate.get("failed")

    def result_error(self, _) -> bool:
        return self.aggregate.has_error()

    def complete(self, _) -> bool:
        return self.aggregate.get("complete")

    def all_started(self, _) -> bool:
        return self.aggregate.get("all_started")

    def lval(self, val: List[str]) -> Callable:
        func_name = f"_{val[0]}"

        if not hasattr(self, func_name):
            raise FilterParseError(f"Invalid selector: {val[0]}")

        return getattr(self, func_name)

    def comp_expression(self, exp: List) -> bool:
        func, comp, rval = tuple(exp)
        comp = comp_str_to_symbol(comp.data)

        return func(comp, rval)

    def arbitrary_string(self, astr: List[Token]) -> str:
        return str(astr[0])

    def CNAME(self, cname: Token) -> str:
        return str(cname)

    def NUMBER(self, num: Token) -> float:
        return float(num)

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
