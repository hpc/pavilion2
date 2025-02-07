from typing import Union, Tuple, List, NewType, Iterator

# from pavilion.micro import flatten
from micro import flatten


TestID = NewType("TestID", Union[int, str])
SeriesID = NewType("SeriesID", Union[int, str])
TestRange = NewType("TestRange", Union[Tuple[int, int], str])
SeriesRange = NewType("SeriesRange", Union[Tuple[int, int], str])


def str_to_range(range_str: str) -> Union[TestRange, SeriesRange]:
    """Convert a string representing either a test or series range into the appropriate range
    object, performing validation along the way."""

    range_str = range_str.lower()

    if range_str == "all":
        return range_str.low

    ends = range_str.split('-')

    if len(ends) != 2:
        raise ValueError(f"Range must be specified by two values. Received: {range_str}.")

    start, end = ends

    if len(start) > 0 and start[0] == 's' and \
        len(end) > 0 and end[0] =='s':
            range_type = SeriesRange
            start = start[1:]
            end = end[1:]
    else:
        range_type = TestRange

    return range_type((int(start), int(end)))


def expand_range(rng: Union[TestRange, SeriesRange]) \
                    -> Union[Iterator[TestRange], Iterator[SeriesRange]]:
    """Convert a range object to a sequence of its constituent IDS."""
    
    if isinstance(rng, TestRange):
        id_type = TestID
    else:
        id_type = SeriesID

    if rng == "all":
        return id_type("all")

    # Ranges are inclusive
    ids = range(rng[0], rng[1] + 1)

    return map(id_type, ids)


def expand_ranges(ranges: Iterator[str]) -> Iterator[str]:
    """Given a sequence of test and series ranges, expand them
    into a sequence of individual tests and series."""

    return flatten(map(expand_range, ranges))
