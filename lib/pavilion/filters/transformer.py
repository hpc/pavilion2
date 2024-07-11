# pylint: disable=no-self-use
# pylint: disable=invalid-name

from datetime import datetime
from typing import Any, List, Optional, Mapping, Iterator

from lark import Transformer, Discard, Token

from pavilion.test_run import TestRun

from .validators import (validate_int, validate_glob, validate_glob_list,
    validate_str_list, validate_datetime, validate_str, validate_name_glob)
from .errors import FilterParseError
from .common import ThreeValue


MICROSECS_PER_SEC = 10**6

SPECIAL_FUNCS = {
    'passed': lambda x: x.get('result') == TestRun.PASS,
    'failed': lambda x: x.get('result') == TestRun.FAIL,
    'has_error': lambda x: x.get('result') == TestRun.ERROR,
}


class FilterTransformer(Transformer):
    """Lark Transformer object for reducing the parse tree to a single boolean
    value after the filter query has been parsed."""

    def __init__(self, attrs: Mapping):
        super().__init__()
        self.attrs = attrs

    def expr(self, expr: List[ThreeValue]) -> bool:
        """Top level rule for parsing. This is called on the root of
        the parse tree only after the rest of the tree has been evaluated."""
        if expr[0] is None:
            return False

        return expr[0]

    def paren_expr(self, expr: List[ThreeValue]) -> bool:
        """Returns the value of a parenthetical expression."""

        return expr[0]

    def or_expr(self, expr: List[Any]) -> ThreeValue:
        """Called on OR expressions (which may or may not actually
        contain the OR connective). Implements a 3-valued logic,
        where a value of None is only returned if all operands
        are None. Otherwise, the operator behaves as if it is
        a 2-valued OR operator and the None values have been removed
        from the list of operands."""

        bools = list(filter(lambda x: isinstance(x, bool), expr))

        if len(bools) > 0:
            return any(bools)

    def and_expr(self, expr: List[Any]) -> bool:
        """Called on AND expressions (which may or may not actually
        contain the AND connective). Implements a 3-valued logic,
        where None is treated as False (for the purposed of AND only)."""

        if None in expr:
            return False

        bools = filter(lambda x: isinstance(x, bool), expr)

        return all(bools)

    def not_expr(self, expr: List[Any]) -> ThreeValue:
        """Called on NOT expressions (which may or may not actually
        contain the NOT operator). Implements a 3-valued logic,
        where not None evaluates to None."""

        if len(expr) == 1:
            return expr[0]

        if expr[1] is None:
            return None

        return not expr[1]

    def comp_expr(self, expr: List[Any]) -> ThreeValue:
        """Called on comparison expressions. Fetches the value
        associated with the particular keyword, then evaluates
        the comparison statement against that value, given the
        provided operator and righthand value."""

        func_name, operator, rval = tuple(expr)

        return getattr(self, func_name)(operator, rval)

    def special(self, special: List[Token]) -> ThreeValue:
        """Called on special values. Determines what boolean function
        to call based on the specific special value, then calls it
        on the Mapping object."""

        name = str(special[0]).lower()
        func = SPECIAL_FUNCS.get(name, lambda x: x.get(name))

        return func(self.attrs)

    def keyword(self, kw: List[Token]) -> str:
        """Converts a keyword token into the name of the corresponding
        function."""

        return f"_{str(kw[0]).lower()}"

    def GLOB(self, glob: Token) -> str:
        """Converts a GLOB token into a string."""

        return str(glob)

    def NUMBER(self, num: Token) -> float:
        """Converts a NUMBER token into a float."""

        return float(num)

    def INT(self, num: Token) -> int:
        """Converts an INT token into a integer."""

        return int(num)

    def WS(self, ws) -> Discard:
        """Discards whitespace tokens."""

        return Discard

    def LT(self, _) -> str:
        """Converts a less-than token into the corresponding symbol."""

        return "<"

    def GT(self, _) -> str:
        """Converts a greater-than token into the corresponding symbol."""

        return ">"

    def LT_EQ(self, _) -> str:
        """Converts a less-than-or-equal token into the corresponding symbol."""

        return "<="

    def GT_EQ(self, _) -> str:
        """Converts a greater-than-or-equal token into the corresponding symbol."""

        return ">="

    def EQ(self, _) -> str:
        """Converts an 'equal' token into the corresponding symbol."""
        return  "="

    def NOT_EQ(self, _) -> str:
        """Converts a not-equal token into the corresponding symbol."""

        return "!="

    def TIMESTAMP(self, ts: Token) -> str:
        """Converts a timestamp token into a string."""

        return str(ts)

    def duration(self, dur: List[Token]) -> str:
        "Converts a duration (e.g. '3 weeks') into a string."""

        mag = str(dur[0])
        unit = str(dur[1])

        return f"{mag} {unit}"

    @validate_int
    def _num_nodes(self) -> int:
        """Fetch the number of nodes on which the test or series ran."""

        return len(self.attrs.get("node_list", []))

    @validate_name_glob
    def _name(self) -> Optional[str]:
        """Fetch the name of the test or series."""

        return self.attrs.get("name")

    @validate_glob
    def _user(self) -> Optional[str]:
        """Fetch the name of the user who ran the test or series."""

        return self.attrs.get("user")

    @validate_glob
    def _sys_name(self) -> Optional[str]:
        """Fetch the name of the host on which the test or series ran."""

        return self.attrs.get("sys_name")

    @validate_glob_list
    def _nodes(self) -> List[str]:
        """Fetch the list of nodes on which the test or series ran."""

        return self.attrs.get("node_list", [])

    @validate_str_list
    def _has_state(self) -> Iterator[str]:
        """Fetch the state history of the test or series."""

        history = self.attrs.get("state_history", [])

        return map(lambda x: x.state, history)

    @validate_datetime
    def _created(self) -> Optional[datetime]:
        """Fetch the date and time at which the test or series
        was created."""

        created = self.attrs.get('created')

        if isinstance(created, float):
            return datetime.fromtimestamp(created)

        return created

    @validate_str
    def _state(self) -> Optional[str]:
        """Fetch the current state of the test or series."""

        state = self.attrs.get("state")

        if state is not None:
            return self.attrs.get("state").state

    @validate_datetime
    def _started(self) -> Optional[datetime]:
        """Fetch the date and time at which the test or series was
        started."""

        started = self.attrs.get('started')

        if isinstance(started, float):
            return datetime.fromtimestamp(started)

        return started

    @validate_datetime
    def _finished(self) -> Optional[datetime]:
        """Fetch the date and time at which the test or series finished."""

        finished = self.attrs.get('finished')

        if isinstance(finished, float):
            return datetime.fromtimestamp(finished)

        return finished

    @validate_glob
    def _partition(self) -> Optional[str]:
        """Fetch the partition on which the test or series ran."""

        return self.attrs.get('partition')
