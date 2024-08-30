from datetime import date, time, datetime, timedelta
from calendar import monthrange
from typing import Tuple, Union


MICROSECS_PER_SEC = 10**6
MONTHS_PER_YEAR = 12
UNITS = ('seconds', 'minutes', 'hours', 'days', 'weeks', 'months', 'years')


def parse_time(rval: str) -> datetime:
    """Parse a string as a time, which may be either a (partial) ISO 8601 timestamp
    or a relative duration (e.g. '3 weeks'), which is interpreted as a time in the past
    (i.e. '3 weeks ago')."""

    rval = rval.strip()

    try:
        return parse_duration(rval, datetime.now())
    except ValueError:
        return parse_iso_timestamp(rval)


def parse_iso_timestamp(rval: str) -> datetime:
    """Parse a string as a (partial) ISO 8601 timestamp. Timetamps
    that do not include all components (month, date, year, etc.) are
    valid, but if a timestamp includes a component, it must also include
    all components of larger magnitude as well. That is, if it includes
    a value for the day of the month, it must also include values
    for month and year. If time is included, all time values (hours,
    minutes, and seconds) must be present."""

    iso_comps = rval.split("T")

    if len(iso_comps) == 2:
        date_str, time_str = tuple(iso_comps)
        date = parse_iso_date(date_str)
        time = parse_iso_time(time_str)
    else:
        date = parse_iso_date(iso_comps[0])
        time = datetime.min.time()

    return datetime.combine(date, time)


def parse_duration(rval: str, now: datetime) -> datetime:
    """Parse a string as a duration relative to the current date and time,
    specified in natural language. A duration consists of an integer magnitude
    and a unit (e.g. 'weeks'), which is optionally plural. A space may optionally
    be included between the magnitude and unit."""

    dur_comps = split_duration(rval)

    if len(dur_comps) == 2:
        mag, unit = tuple(dur_comps)
    else:
        raise ValueError(f"Unable to parse duration {rval}.")

    mag = int(mag)
    unit = normalize(unit)

    if unit not in UNITS:
        raise ValueError(f"Invalid unit {unit} for duration")

    if unit not in ("years", "months"):
        return now - timedelta(**{unit: mag})

    new_day = now.day

    if unit == 'years':
        new_year = now.year - mag
        new_month = now.month

    if unit == 'months':
        dyear, dmonth = divmod(mag, MONTHS_PER_YEAR)
        new_year = now.year - dyear
        new_month = (now.month - dmonth) % MONTHS_PER_YEAR

    max_day = monthrange(new_year, new_month)[1]

    if new_day > max_day:
        new_day = max_day

    return now.replace(year=new_year, month=new_month, day=new_day)



def parse_iso_date(rval: str) -> date:
    """Parse and ISO date format, which has the form YYYY-MM-DD. The month
    and day are optional, and default to January and the first of the month
    respectively if not provided."""

    date_comps = tuple(map(int, rval.split("-")))

    month = 1
    day = 1

    year = date_comps[0]

    if len(date_comps) > 1:
        month = date_comps[1]
    if len(date_comps) > 2:
        day = date_comps[2]

    return date(year, month, day)


def parse_iso_time(rval: str) -> time:
    """Parse the ISO time format, which is a colon-separated triple
    of hours, minutes, and seconds, where hours and minutes are integers,
    and seconds is a floating-point value. Unlike the date, all values
    are required."""

    time_comps = rval.split(":")

    if len(time_comps) == 3:
        hrs, mins, secs = tuple(time_comps)
        secs = float(secs)
        time_comps[2] = secs
        microsecs = (secs - int(secs)) * MICROSECS_PER_SEC
        time_comps.append(microsecs)

    iso = tuple(map(int, time_comps))

    return time(*iso)


def split_duration(rval: str) -> Tuple[str, str]:
    """Split a relative duration into its magnitude
    and unit components."""

    if " " in rval:
        return tuple(rval.split())

    for i, elem in enumerate(rval):
        if elem.isalpha():
            return rval[:i], rval[i:]

    return rval


def normalize(unit: str) -> str:
    """Normalize a unit string (e.g. weeks, months,
    years) by pluralizing it and converting it to
    lower case."""

    unit = unit.lower()

    if unit[-1] != "s":
        return unit + "s"

    return unit
