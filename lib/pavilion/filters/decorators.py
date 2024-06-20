"""Defines decorators used by the filter transformer for validating input types
and determining which functions to dispatch"""

from fnmatch import fnmatch
from typing import Any, Callable, List

from .filters import FilterParseError

id_func = lambda x, y: x
all_match = lambda x, y: all(map(lambda z: fnmatch(z, y), x))

def validate_int(func: Callable[[object], Any]) -> Callable[[object, str, str], bool]:
    """Decorator for methods defined on FilterTransformer whose return values are
    expected to be compared against integers, used in parsing expressions. The
    function returned from this decorator takes the comparator and righthand
    operands (still in the form of strings) as its arguments, checks that the
    righthand operand can be parsed as an integer, then performs the comparison
    specified by the comparator string against the output of the decorated function.
    If the validation fails, or if the comparator string does not specify a valid
    comparison operator, raises a FilterParseError."""
    
    def ifunc(self, comp: str, rval: str) -> bool:
        try:
            rval = int(rval)
        except ValueError:
            raise FilterParseError(f"Invalid value {rval} for integer operation")

        lval = func(self)

        if comp == '=':
            return lval == rval
        elif comp == '<':
            return lval < rval
        elif comp == '>':
            return lval > rval
        elif comp == '<=':
            return lval <= rval
        elif comp == '>=':
            return lval >= rval
        elif comp == '!=':
            return lval != rval
        else:
            raise FilterParseError(f"Invalid comparator for type int: {comp}")

    return ifunc

def validate_glob(func: Callable[[object], str]) -> Callable[[object, str, str], bool]:
    """Decorator for methods defined on FilterTransformer whose return values are
    expected to be compared against globs, used in parsing expressions. The function
    returned from this decorator takes the comparator and righthand operands (still in
    the form of strings) as its arguments, then performs the comparison specified by
    the comparator string. If the validation fails, or if the comparator string does
    not specify a valid comparison operation, raises a FilterParseError."""
    
    def gfunc(self, comp: str, rval: str) -> bool:
        lval = func(self).lower()
        rval = rval.lower()

        if comp == '=':
            return fnmatch(lval, rval)
        elif comp == '!=':
            return not fnmatch(lval, rval)
        else:
            raise FilterParseError(f"Invalid comparator for type str: {comp}")

    return gfunc

def validate_glob_list(func: Callable[[object], List[str]]) -> Callable[[object, str, str], bool]:
    """Decorator for methods defined on FilterTransformer whose return values are lists,
    the elements of which are expected to be compared against globs. The function
    returned from this decorator takes the comparator and righthand operands (still in
    the form of strings) as its arguments, then performs the comparison specified by the
    comparator string. If the validation fails, or if the comparator string does not
    specify a valid comparison operation, raises a FilterParseError."""

    def glfunc(self, comp: str, rval: str) -> bool:
        lval = func(self)
        rval = rval.lower()

        if comp == '=':
            return all(map(lambda x: fnmatch(x.lower(), rval), lval))
        else:
            raise FilterParseError(f"Invalid comparator for type str: {comp}")

    return glfunc

def validate_str_list(func: Callable[[object], List[str]]) -> Callable[[object, str, str], bool]:
    
    def slfunc(self, comp: str, rval: str) -> bool:
        lval = map(lambda x: x.lower(), func(self))

        if comp == '=':
            return any(map(lambda x: x == rval.lower(), lval))
        else:
            raise FilterParseError(f"Invalid comparator for type str: {comp}")

    return slfunc

