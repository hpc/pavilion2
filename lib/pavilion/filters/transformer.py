from datetime import date, time, datetime, timedelta
from typing import Any, Callable, Dict, Union, List

from pavilion.status_file import STATES, SERIES_STATES, TestStatusFile, TestStatusInfo
from pavilion.test_run import TestRun

from .attr_getter import AttributeGetter
from .validators import (validate_int, validate_glob, validate_glob_list, validate_str_list, validate_datetime, validate_str, validate_name_glob)
from .errors import FilterParseError

from lark import Transformer, Discard, Token


MICROSECS_PER_SEC = 10**6

SPECIAL_FUNCS = {
    'passed': lambda x: x.get('result') == TestRun.PASS,
    'failed': lambda x: x.get('result') == TestRun.FAIL,
    'has_error': lambda x: x.get('result') == TestRun.ERROR,
}


class FilterTransformer(Transformer):

    def __init__(self, attrs: AttributeGetter):
        self.attrs = attrs

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
        name = str(special[0]).lower()
        func = SPECIAL_FUNCS.get(name, lambda x: x.get(name))

        return func(self.attrs)

    def keyword(self, kw: List[Token]) -> str:
        return f"_{str(kw[0]).lower()}"

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
        return len(self.attrs.get("nodes"))

    @validate_name_glob
    def _name(self) -> str:
        return self.attrs.get("name", "")

    @validate_glob
    def _user(self) -> str:
        return self.attrs.get("user")

    @validate_glob
    def _sys_name(self) -> str:
        return self.attrs.get("sys_name")

    @validate_glob_list
    def _nodes(self) -> List[str]:
        return self.attrs.get("nodes")

    @validate_str_list
    def _has_state(self) -> List[str]:
        return map(lambda x: x.state, self.attrs.get("state_history"))

    @validate_datetime
    def _created(self) -> datetime:
        return self.attrs.get("created")

    @validate_str
    def _state(self) -> str:
        return self.attrs.get("state").state
