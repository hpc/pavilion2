from typing import Union, Tuple, List, Iterable, Optional
from abc import ABC, abstractmethod

from pavilion.micro import flatten, unique
from pavilion.utils import is_int


class ID(ABC):
    """Base class for IDs"""

    def __init__(self, id_str: str):
        self.id_str = id_str

    @staticmethod
    @abstractmethod
    def is_valid_id(id_str: str) -> bool:
        """Determine whether the given string constitutes a valid ID."""

        raise NotImplementedError

    def __str__(self) -> str:
        return self.id_str

    def __eq__(self, other: "ID") -> bool:
        return self.id_str == other.id_str

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id_str})"

    def __hash__(self) -> int:
        return hash(self.id_str)


class TestID(ID):
    """Represents a single test ID."""

    @classmethod
    def is_valid_id(cls, id_str: str) -> bool:
        """Determine whether the given string constitutes a valid test ID."""

        test_num = -1

        if "." in id_str:
            test_num = int(id_str.split(".")[-1])
        elif is_int(id_str):
            test_num = int(id_str)

        return test_num > 0

    def is_int(self) -> bool:
        """Determine whether the test ID is an integer value."""

        return is_int(self.id_str)

    def as_int(self) -> int:
        """Convert the test ID into an integer, if possible."""

        try:
            return int(self.id_str)
        except:
            raise ValueError(f"Test with ID {self.id_str} cannot be converted to an integer.")

    @property
    def parts(self) -> Tuple[str]:
        """Return a tuple of components of the test ID, where components are separated by
        periods."""

        return tuple(self.id_str.split('.', 1))

    @property
    def label(self) -> str:
        """Return the config label component of the test ID."""

        if len(self.parts) > 1:
            return self.parts[0]

        return "main"

    @property
    def test_num(self) -> Optional[int]:
        """Return the test number component of the test ID."""

        if self.is_int():
            return self.as_int()
        elif len(self.parts) > 1:
            return int(self.parts[-1])


class SeriesID(ID):
    """Represents a single series ID."""

    @classmethod
    def is_valid_id(cls, id_str: str) -> bool:
        """Determine whether the given string constitutes a valid series ID."""

        return cls.is_abstract_id(id_str) or (len(id_str) > 0 and id_str[0] == 's' \
            and is_int(id_str[1:]) and int(id_str[1:]) > 0)

    @staticmethod
    def is_abstract_id(id_str: str) -> bool:
        """Determine whether the given string is an abstract ID, that is, whether it
        is 'last' or 'all'."""

        return id_str.lower() in ("last", "all")

    @classmethod
    def is_concrete_id(cls, id_str: str) -> bool:
        """Determine whether the given string is a concrete ID, that is, whether it
        is not 'last' or 'all'."""

        return cls.is_valid_id(id_str) and not cls.is_abstract_id(id_str)

    def all(self) -> bool:
        """Determine whether the ID is the set of all IDs."""

        return self.id_str.lower() == "all"

    def last(self) -> bool:
        """Determine whether the ID is the most recently run."""

        return self.id_str.lower() == "last"

    def is_int(self) -> bool:
        """Determine whether the series ID is an integer value."""

        return len(self.id_str) > 0 and is_int(self.id_str[1:])

    def as_int(self) -> int:
        """Convert the series ID into an integer, if possible."""

        if self.all() or self.last():
            raise ValueError(f"Series with ID {self.id_str} cannot be converted to an integer.")

        return int(self.id_str[1:])


class GroupID:
    """Represents a single group ID."""

    def __init__(self, id_str: str):
        self.id_str = id_str

    @staticmethod
    def is_valid_id(id_str: str) -> bool:
        """Determine whether the given string constitutes a valid group ID."""
        return len(id_str) > 0 and not (TestID.is_valid_id(id_str) or SeriesID.is_valid_id(id_str))

    def __str__(self) -> str:
        return self.id_str

    def __eq__(self, other: "GroupID") -> bool:
        return self.id_str == other.id_str

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id_str})"


class IDRange(ABC):
    """Represents a contiguous sequence of IDs."""

    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    @staticmethod
    @abstractmethod
    def is_valid_range_str(rng_str: str) -> bool:
        """Determine whether the given string constitutes a valid range."""

        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def from_str(rng_str: str) -> "IDRange":
        """Produce a new range object from a string.

        NOTE: This method should not perform validation. It assumes that validation has been
        performed prior to being called."""

        raise NotImplementedError

    @abstractmethod
    def expand(self) -> List[ID]:
        """Get the sequence of all values in the range."""

        raise NotImplementedError

    def __eq__(self, other: "IDRange") -> bool:
        if not isinstance(other, type(self)):
            return False

        return self.start == other.start and self.end == other.end

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.start}, {self.end})"


class TestRange(IDRange):
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
        """Produce a new test range object from a string. Assumes validation has been performed
        prior to being called."""

        start, end = rng_str.split('-')

        return TestRange(int(start), int(end))

    def expand(self) -> List[TestID]:
        """Get the sequence of all series IDs in the range."""

        return list(map(TestID, map(str, range(self.start, self.end + 1))))

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


class SeriesRange(IDRange):
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
        """Produce a new series range object from a string. Assumes validation has been performed
        prior to being called."""

        start, end = rng_str.split('-')

        return SeriesRange(int(start[1:]), int(end[1:]))

    def expand(self) -> List[SeriesID]:
        """Get the sequence of all series IDs in the range."""

        return list(map(SeriesID, map(lambda x: f"s{x}", range(self.start, self.end + 1))))

    def __str__(self) -> str:
        return f"s{self.start}-s{self.end}"


def multi_convert(id_str: str) -> Union[List[TestID], List[SeriesID], List[GroupID]]:
    """Convert a string into a list (possibly a singleton list) of either a TestID, SeriesID,
    or GroupID as appropriate."""

    if id_str.lower() == "all":
        return [SeriesID("all")]
    if id_str.lower() == "last":
        return [SeriesID("last")]

    if TestRange.is_valid_range_str(id_str):
        return list(TestRange.from_str(id_str).expand())
    if SeriesRange.is_valid_range_str(id_str):
        return list(SeriesRange.from_str(id_str).expand())
    if TestID.is_valid_id(id_str):
        return [TestID(id_str)]
    if SeriesID.is_valid_id(id_str):
        return [SeriesID(id_str)]

    return [GroupID(id_str)]


def resolve_mixed_ids(ids: Iterable[str],
                      auto_last: bool = True) -> List[Union[TestID, SeriesID, GroupID]]:
    """Fully resolve all IDs in the given list into either test IDs, series IDs, or group IDs."""

    ids = list(ids)

    if auto_last and len(ids) == 0:
        return [SeriesID("last")]

    if "all" in ids:
        return [SeriesID("all")]

    return list(flatten(map(multi_convert, ids)))
