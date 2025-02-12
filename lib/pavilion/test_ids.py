from typing import Union, Tuple, List, NewType, Iterator, TypeVar, Iterable
from abc import abstractmethod

# from pavilion.micro import flatten
from pavilion.micro import flatten, listmap
from pavilion.utils import is_int


class ID:
    """Base class for IDs"""

    def __init__(self, id_str: str):
        self.id_str = id_str

    # pylint: disable=no-self-argument
    @abstractmethod
    def is_valid_id(id_str: str) -> bool:
        """Determine whether the given string constitutes a valid ID."""
        ...

    def __str__(self) -> str:
        return self.id_str

    def __eq__(self, other: "ID") -> bool:
        return self.id_str == other.id_str

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id_str})"


class TestID(ID):
    """Represents a single test ID."""

    @staticmethod
    def is_valid_id(id_str: str) -> bool:
        """Determine whether the given string constitutes a valid test ID."""

        return '.' in id_str or (is_int(id_str) and int(id_str) > 0)

    def is_int(self):
        """Determine whether the test ID is an integer value."""

        return is_int(self.id_str)

    def as_int(self):
        """Convert the test ID into an integer, if possible."""

        try:
            return int(self.id_str)
        except:
            raise ValueError(f"Test with ID {self.id_str} cannot be converted to an integer.")

    @property
    def parts(self) -> List[str]:
        """Return a list of components of the test ID, where components are separated by
        periods."""

        return self.id_str.split('.', 1)


class SeriesID(ID):
    """Represents a single series ID."""

    @staticmethod
    def is_valid_id(id_str: str) -> bool:
        """Determine whether the given string constitutes a valid series ID."""

        return id_str == 'all' or id_str == 'last' or (len(id_str) > 0 and id_str[0] == 's' \
            and is_int(id_str[1:]) and int(id_str[1:]) > 0)

    def is_int(self):
        """Determine whether the series ID is an integer value."""

        return len(self.id_str) > 0 and is_int(self.id_str[1:])

    def as_int(self):
        """Convert the series ID into an integer, if possible."""

        if self.all() or self.last():
            raise ValueError(f"Series with ID {self.id_str} cannot be converted to an integer.")

        return int(self.id_str[1:])

    def all(self):
        """Determine whether the series is the set of all tests."""

        return self.id_str == "all"

    def last(self):
        """Determine whether the series is the most recently run."""

        return self.id_str == "last"


class GroupID(ID):
    """Represents a single group ID."""

    @staticmethod
    def is_valid_id(id_str: str) -> bool:
        """Determine whether the given string constitutes a valid group ID."""
        return len(id_str) > 0 and not (TestID.is_valid_id(id_str) or SeriesID.is_valid_id(id_str))


class Range:
    """Represents a contiguous sequence of IDs."""

    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    # pylint: disable=no-self-argument
    @abstractmethod
    def is_valid_range_str(rng_str: str) -> bool:
        """Determine whether the given string constitutes a valid range."""
        ...

    # pylint: disable=no-self-argument
    @abstractmethod
    def from_str(rng_str: str) -> "Range":
        """Produce a new range object from a string."""
        ...

    @abstractmethod
    def expand(self) -> Iterator:
        """Get the sequence of all values in the range."""
        ...

    @abstractmethod
    def __str__(self) -> str:
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.start}, {self.end})"


class TestRange(Range):
    """Represents a contiguous sequence of test IDs."""

    @staticmethod
    def is_valid_range_str(rng_str: str) -> bool:
        """Determine whether the given string constitutes a valid test range."""

        rng_str = rng_str.split('-')

        if len(rng_str) != 2:
            return False

        start, end = rng_str

        if not (is_int(start) and is_int(end)):
            return False
        if not (int(start) > 0 and int(end) > 0):
            return False

        # Allow degenerate ranges
        return int(end) - int(start) >= 0

    @staticmethod
    def from_str(rng_str: str) -> "TestRange":
        """Produce a new test range object from a string."""

        start, end = rng_str.split('-')

        return TestRange(int(start), int(end))

    def expand(self) -> Iterator["TestRange"]:
        """Get the sequence of all series IDs in the range."""

        return map(TestID(map(str, range(self.start, self.end + 1))))

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


class SeriesRange(Range):
    """Represents a contiguous sequence of series IDs."""

    @staticmethod
    def is_valid_range_str(rng_str: str) -> bool:
        rng_str = rng_str.split('-')

        if len(rng_str) != 2:
            return False

        start, end = rng_str

        if not (is_int(start[1:]) and is_int(end[1:])):
            return False
        if not (int(start[1:]) > 0 and int(end[1:]) > 0):
            return False

        # Allow degenerate ranges
        return int(end[1:]) - int(start[1:]) >= 0

    @staticmethod
    def from_str(rng_str: str) -> "SeriesRange":
        """Produce a new series range object from a string."""

        start, end = rng_str.split('-')

        return SeriesRange(int(start[1:]), int(end[1:]))

    def expand(self) -> Iterator["TestRange"]:
        """Get the sequence of all series IDs in the range."""

        return map(SeriesID, map(lambda x: f"s{x}", range(self.start, self.end + 1)))

    def __str__(self) -> str:
        return f"s{self.start}-s{self.end}"


def multi_convert(id_str: str) -> Union[List[TestID], List[SeriesID], List[GroupID]]:
    """Convert a string into a list (possibly a singleton list) of either a TestID, SeriesID,
    or GroupID as appropriate."""

    if TestRange.is_valid_range_str(id_str):
        return list(TestRange.from_str(id_str).expand())
    if SeriesRange.is_valid_range_str(id_str):
        return list(SeriesRange.from_str(id_str).expand())
    if TestID.is_valid_id(id_str):
        return [TestID(id_str)]
    if SeriesID.is_valid_id(id_str):
        return [SeriesID(id_str)]

    return [GroupID(id_str)]


def resolve_ids(ids: Iterable[str]) -> List[Union[TestID, SeriesID, GroupID]]:
    """Fully resolve all IDs in the given list into either test IDs, series IDs, or group IDs."""

    ids = list(ids)

    if "all" in ids:
        return [SeriesID("all")]

    ids = (i for i in ids if i != "all")

    return list(flatten(map(multi_convert, ids)))
