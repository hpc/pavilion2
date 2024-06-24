from datetime import date, time, datetime, timedelta
from typing import Tuple, Union


MICROSECS_PER_SEC = 10**6
UNITS = ('seconds', 'minutes', 'hours', 'days', 'weeks')


def parse_time(rval: str) -> datetime:
    rval = rval.strip()

    try:
        return parse_duration(rval)
    except ValueError:
        return parse_iso(rval)


def parse_iso(rval: str) -> Union[date, datetime]:
    iso_comps = rval.split("T")

    if len(iso_comps) == 2:
        date_str, time_str = tuple(iso_comps)
        date = parse_iso_date(date_str)
        time = parse_iso_time(time_str)
    else:
        date = parse_iso_date(iso_comps[0])
        time = datetime.min.time()
    
    return datetime.combine(date, time)


def parse_duration(rval: str) -> datetime:
    dur_comps = split_duration(rval)

    if len(dur_comps) == 2:
        mag, unit = tuple(dur_comps)
    else:
        raise ValueError(f"Unable to parse duration {rval}.")

    mag = int(mag)
    unit = normalize(unit)

    if unit not in UNITS:
        raise ValueError(f"Invalid unit {unit} for duration")

    # TODO: Implement logic for months and years (timedelta does not support)
    return datetime.now() - timedelta(**{unit: mag})


def parse_iso_date(rval: str) -> date:
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
    if " " in rval:
        return tuple(rval.split())

    for i, e in enumerate(rval):
        if e.isalpha():
            return rval[:i], rval[i:]

    return rval


def normalize(unit: str) -> str:
    unit = unit.lower()

    if unit[-1] != "s":
        return unit + "s"

    return unit
