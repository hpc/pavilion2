# pylint: disable=invalid-name

import re
import uuid
from typing import Union, Tuple, List, Iterable, Optional, Dict, Any, TextIO
from abc import ABC, abstractmethod

from pavilion.utils import is_int, is_hash
from pavilion.errors import PavilionError


HASH_LEN = 32


class TestIDError(PavilionError):
    """Error related to the manipulation and resolution of test IDs."""


class ID(ABC):
    """Base class for IDs"""

    def __init__(self, id_str: str):
        if not self.is_valid_id(id_str):
            raise ValueError(f"Invalid string {id_str} for type {self.__class__.__name__}.")

        self.id_str = id_str

    @classmethod
    @abstractmethod
    def is_valid_id(cls, id_str: str) -> bool:
        """Determine whether the given string constitutes a valid ID."""

        raise NotImplementedError

    def __str__(self) -> str:
        return self.id_str

    def __eq__(self, other: Any) -> bool:
        if not hasattr(other, "id_str"):
            return False

        return self.id_str.lower() == other.id_str.lower()

    @abstractmethod
    def __gt__(self, other: "ID") -> bool:
        raise NotImplementedError

    def __lt__(self, other: "ID") -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(f"Incompatible type for comparison with {self.__class__.__name__}: "\
                            f"{type(other).__name__}.")

        return not (self > other or self == other)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id_str})"

    def __hash__(self) -> int:
        return hash(self.id_str)


class TestID(ID):
    """Represents a single test ID."""

    def __init__(self, id_str: str):
        super().__init__(id_str)

        parts = self.id_str.split('.', 1)

        if len(parts) == 2:
            self.series = SeriesID(parts[0])
            self.id = int(parts[1])
        else:
            self.series = None

            if is_int(parts[0]):
                self.id = int(parts[0])
            else:
                self.id = parts[0]

        self.parts = (self.series, self.id)

    @classmethod
    def is_valid_id(cls, id_str: str) -> bool:
        """Determine whether the given string constitutes a valid test ID."""

        if is_hash(id_str, HASH_LEN) or is_int(id_str):
            return True

        if "." in id_str:
            series_id_str, num_str = id_str.split(".", 1)

            test_num = -1

            if is_int(num_str):
                test_num = int(num_str)

            return test_num >= 0 and SeriesID.is_valid_id(series_id_str)

        return False

    def is_absolute(self) -> bool:
        """Returns true if the ID is absolute (i.e. not series-relative)."""

        return self.series is None

    def is_relative(self) -> bool:
        """Returns true if the ID is relative to a particular series."""

        return not self.is_absolute()

    @classmethod
    def new(cls) -> "TestID":
        """Randomly generate a new test ID."""

        return cls(uuid.uuid4().hex)

    def next(self) -> "TestID":
        """Get the next ID after this one."""

        if self.is_absolute():
            raise ValueError(f"Absolute TestID {self} has no well-defined next ID.")

        return self.__class__(f"{self.series}.{self.id + 1}")

    def __gt__(self, other: "TestID") -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(f"Incompatible type for comparison with {self.__class__.__name__}: "\
                            f"{type(other).__name__}.")

        if self.is_absolute() and other.is_absolute():
            return int(self.id_str, 16) > int(other.id_str, 16)
        elif self.is_relative() and other.is_relative():
            if self.series == other.series:
                return int(self.id) > int(other.id)
            else:
                raise ValueError(f"Cannot compare test IDs {self} and {other} "
                                "from different series.")
        else:
            raise ValueError("Incompatible test ID formats for numerical comparison: "\
                            "{self} and {other}")

class SeriesID(ID):
    """Represents a single series ID."""

    @classmethod
    def is_valid_id(cls, id_str: str) -> bool:
        """Determine whether the given string constitutes a valid series ID."""

        return id_str.lower() in ("last", "all") or (len(id_str) > 0 and id_str[0] == 's' \
            and is_int(id_str[1:]) and int(id_str[1:]) > 0)

    def is_abstract_id(self) -> bool:
        """Return true if the ID is an abstract ID, that is, whether it is 'last' or 'all'."""

        return self.all() or self.last()

    def is_concrete_id(self) -> bool:
        """Return true if the ID is a concrete ID, that is, whether it is not 'last' or 'all'."""

        return not self.is_abstract_id()

    def all(self) -> bool:
        """Determine whether the ID is the set of all IDs."""

        return self.id_str.lower() == "all"

    def last(self) -> bool:
        """Determine whether the ID is the most recently run."""

        return self.id_str.lower() == "last"

    def as_int(self) -> int:
        """Convert the series ID into an integer, if possible."""

        if self.is_abstract_id():
            raise ValueError(f"Abstract series '{self}' cannot be converted to an integer.")

        return int(self.id_str[1:])

    @classmethod
    def from_int(cls, id: int) -> "SeriesID":
        """Create a new SeriesID from an int."""

        return cls(f"s{id}")

    def next(self) -> "SeriesID":
        """Get the next SeriesID after this one."""

        return self.__class__(f"s{self.as_int() + 1}")

    def __gt__(self, other: "SeriesID"):
        if not isinstance(other, self.__class__):
            raise TypeError(f"Incompatible type for comparison with {self.__class__.__name__}: "\
                            f"{type(other).__name__}.")

        return self.as_int() > other.as_int()

class GroupID(ID):
    """Represents a single group ID."""

    GROUP_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]+$')

    @classmethod
    def is_valid_id(cls, id_str: str) -> bool:
        """Determine whether the given string constitutes a valid group ID."""
        return not (TestID.is_valid_id(id_str) or \
                    SeriesID.is_valid_id(id_str) or \
                    TestRange.is_valid_range_str(id_str) or \
                    SeriesRange.is_valid_range_str(id_str)) and \
               cls.GROUP_NAME_RE.match(id_str) is not None

    def __gt__(self, other: "GroupID") -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(f"Incompatible type for comparison with {self.__class__.__name__}: "\
                            f"{type(other).__name__}.")

        return self.id_str > other.id_str


class IDRange(ABC):
    """Represents a contiguous sequence of IDs."""

    def __init__(self, start: int, end: int):
        if start > end:
            raise ValueError(f"End value {end} must be greater than or equal to {start}.")
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

    def __len__(self) -> int:
        return self.end - self.start + 1


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

def resolve_mixed_ids(ids: Iterable[str],
                      auto_last: bool = True) -> Dict[str, List[ID]]:
    """Fully resolve all IDs in the given list into either test IDs, series IDs, or group IDs."""

    id_dict = {"tests": [], "series": [], "groups": []}

    ids = list(ids)

    if auto_last and len(ids) == 0:
        id_dict["series"].append(SeriesID("last"))

    if "all" in ids:
        id_dict["series"].append(SeriesID("all"))

        return id_dict

    for id_str in ids:
        if TestID.is_valid_id(id_str):
            id_dict["tests"].append(TestID(id_str))
        elif SeriesID.is_valid_id(id_str):
            id_dict["series"].append(SeriesID(id_str))
        elif GroupID.is_valid_id(id_str):
            id_dict["groups"].append(GroupID(id_str))
        elif TestRange.is_valid_range_str(id_str):
            id_dict["tests"].extend(TestRange.from_str(id_str).expand())
        elif SeriesRange.is_valid_range_str(id_str):
            id_dict["series"].extend(SeriesRange.from_str(id_str).expand())

    return id_dict
