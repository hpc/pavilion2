"""Defines decorators used by the filter transformer for validating input types
and determining which functions to dispatch"""

from fnmatch import fnmatch
from itertools import starmap
from typing import Callable, List, TypeVar

from .errors import FilterParseError
from .parse_time import parse_time
from .common import identity, ThreeValue


T = TypeVar("T")


def make_validator(comp_func: Callable[[T, str, T], bool],
                    rtype: Callable[[str], T] = identity
                    ) -> Callable[[object, str, str], ThreeValue]:
    """Make a decorator that validates a comparison expression, ensuring that its
    righthand operand is of type rtype, produces the lefthand operand by calling
    the decorated function (intended to be a method of FilterTransform), then
    compares the lefthand and righthand operands using comp_func, which also
    takes the expression's operator as an argument."""

    def validate(func: Callable[[object], T]) -> Callable[[object, str, str], bool]:

        def compare(self, comp: str, rval: str) -> bool:
            try:
                rval = rtype(rval)
            except ValueError:
                raise FilterParseError(f"Invalid value {rval} for function {rtype.__name__}.")

            lval = func(self)

            if lval is None:
                return None

            return comp_func(lval, comp, rval)

        return compare

    return validate


def comp_num(lval: int, comp: str, rval: int) -> bool:
    """Compare two integer values according to the provided
    operator string."""

    if comp == '=':
        return lval == rval
    if comp == '!=':
        return lval != rval
    if comp == '<':
        return lval < rval
    if comp == '>':
        return lval > rval
    if comp == '<=':
        return lval <= rval
    if comp == '>=':
        return lval >= rval

    raise FilterParseError(f"Invalid comparator {comp} for numerical type.")


def comp_glob(lval: str, comp: str, rval: str) -> bool:
    """Determine whether the provided glob (passed as the righthand
    value) matches the string (passed as the lefthandvalue). The match
    can be inverted by passing '!=' as the operator rather than '='.
    Uses case-insensitive matching."""

    lval = lval.upper() # fnmatch is case sensitive, despite docs
    rval = rval.upper()

    if comp == '=':
        return fnmatch(lval, rval)
    if comp == '!=':
        return not fnmatch(lval, rval)

    raise FilterParseError(f"Invalid comparator {comp} for (str, glob).")


def comp_glob_list(lval: List[str], comp: str, rval: str) -> bool:
    """Determine whether every element in the provided list matches the
    provided glob. The only valid comparison operator is '=' (since '!='
    would be ambiguous here). Uses case-insensitive matching."""

    if comp != '=':
        raise FilterParseError(f"Invalid comparator {comp} for (List[str], glob).")

    lval = map(lambda x: x.upper(), lval) # fnmatch is case sensitive, despite docs
    rval = rval.upper()

    matches = map(lambda x: fnmatch(x, rval), lval)

    return all(matches)


def comp_str_list(lval: List[str], comp: str, rval: str) -> bool:
    """Determine whether the given string is in the list. Uses case-insensitive
    matching."""

    if comp != '=':
        raise FilterParseError(f"Invalid comparator {comp} for (List[str], str).")

    lval = map(lambda x: x.upper(), lval)
    rval = rval.upper()

    return rval in lval

def comp_str(lval: str, comp: str, rval: str) -> bool:
    """Determine whether the two strings match exactly. The match may
    be inverted by passing '!=' as the operator. Uses case-insensitive
    matching."""

    lval = lval.upper()
    rval = rval.upper()

    if comp == '=':
        return lval == rval
    if comp == '!=':
        return lval != rval

    raise FilterParseError(f"Invalid comparator {comp} for type str.")


def comp_name_glob(lval: str, comp: str, rval: str) -> bool:
    """Determine whether the three-part test name (passed as the lefthand argument)
    matches the name glob (passed as the righthand argument. The operation
    behaves slightly differently than standard globbing, in that it performs
    a component-wise match, where components are separated by periods. Unspecified
    components are treated as wildcards for the purposes of matching."""

    if comp not in ("=", "!="):
        raise FilterParseError(f"Invalid comparator {comp} for name glob.")

    lval = lval.upper() # fnmatch is case sensitive, despite docs
    rval = rval.upper()

    name_comps = lval.split(".")
    pattern_comps = rval.split(".")

    matches = starmap(fnmatch, zip(name_comps, pattern_comps))

    if comp == "=":
        return all(matches)
    else:
        return not all(matches)


# Create all the validators
# Procedural abstraction FTW!
validate_int = make_validator(comp_num, int)
validate_glob = make_validator(comp_glob)
validate_glob_list = make_validator(comp_glob_list)
validate_str_list = make_validator(comp_str_list)
validate_datetime = make_validator(comp_num, parse_time)
validate_str = make_validator(comp_str)
validate_name_glob = make_validator(comp_name_glob)
