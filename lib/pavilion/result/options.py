"""Options and constants common to all result parsers."""

from pathlib import Path
from typing import Dict, Callable, Any, List

from pavilion.utils import auto_type_convert
from .common import EMPTY_VALUES, NON_MATCH_VALUES, normalize_filename


def store_values(stor: dict, keys: str, values: Any) -> List[str]:
    """Store the values under the appropriate keys in the given dictionary
    using the given action.

    For single keys like 'flops', the action modified value is simply stored.

    For complex keys like 'flops, , speed', values is expected to be a list
    of at least this length, and the action modified values are stored in
    the key that matches their index.

    A list of errors/warnings are returned."""

    errors = []

    if ',' in keys:
        keys = [k.strip() for k in keys.split(',')]
        # Strip the last item if it's empty, as it can be used to denote
        # storing a single item from a list.
        if keys[-1] == '':
            keys = keys[:-1]

        if not isinstance(values, list):
            errors.append(
                "Trying to store non-list value in a multi-keyed result.\n"
                "Just storing under the first non-null key.\n"
                "keys: {}\nvalue: {}".format(keys, values))
            keys = [k for k in keys if k and k != '_']
            if not keys:
                errors.append("There was no valid key to store under.")
            else:
                stor[keys[0]] = values

        else:
            values = list(reversed(values))

            if len(values) < len(keys):
                errors.append(
                    "More keys than values for multi-keyed result.\n"
                    "Storing 'null' for missing values.\n"
                    "keys: {}, values: {}".format(keys, values))

            for key in keys:
                val = values.pop() if values else None
                if key and key != '_':
                    stor[key] = val

    else:
        stor[keys] = values

    return errors


ACTION_STORE = 'store'
ACTION_STORE_STR = 'store_str'
ACTION_STORE_SUM = 'store_sum'
ACTION_STORE_MIN = 'store_min'
ACTION_STORE_MED = 'store_med'
ACTION_STORE_MAX = 'store_max'
ACTION_TRUE = 'store_true'
ACTION_FALSE = 'store_false'
ACTION_COUNT = 'count'


def action_store(raw_val):
    """Auto type convert the value, if possible."""
    if raw_val not in EMPTY_VALUES:
        return auto_type_convert(raw_val)
    else:
        return raw_val


def action_count(raw_val):
    """Count the items in raw_val, or set it to None if it isn't a list."""

    if isinstance(raw_val, list):
        return len(raw_val)
    else:
        return None


def action_store_sum(raw_val):
    """Store the sum of the found values."""

    if isinstance(raw_val, list):
        val_sum = None
        for val in raw_val:
            val = auto_type_convert(val)
            if isinstance(val, (int, float)):
                if val_sum is None:
                    val_sum = val
                else:
                    val_sum += val
        return val_sum
    else:
        return None

def action_store_min(raw_val):
    """Stores the min of the found values."""

    if isinstance(raw_val, list):
        val_min = None
        for val in raw_val:
            val = auto_type_convert(val)
            if isinstance(val, (int, float)):
                if val_min is None:
                    val_min = val
                else:
                    if val_min > val:
                        val_min = val
        return val_min
    else:
        return None

def action_store_med(raw_val):
    """Stores the medium of the found values."""

    if isinstance(raw_val, list):
        val_med = None
        values = []
        for val in raw_val:
            val = auto_type_convert(val)
            if isinstance(val, (int, float)):
                values.append(val)

        values.sort()
        values_length = len(values)
        if not values_length % 2 == 0:
            val_med = values[(values_length // 2) - 1]
        else:
            middle_val = values[(values_length // 2) - 1]
            middle_val_2  = values[(values_length // 2)]
            val_med = (middle_val + middle_val_2) / 2

        return val_med
    else:
        return None

def action_store_max(raw_val):
    """Stores the maximum of the found values."""

    if isinstance(raw_val, list):
        val_max = None
        for val in raw_val:
            val = auto_type_convert(val)
            if isinstance(val, (int, float)):
                if val_max is None:
                    val_max = val
                else:
                    if val_max < val:
                        val_max = val
        return val_max
    else:
        return None

# Action functions should take the raw value and convert it to a final value.
ACTIONS = {
    ACTION_STORE: action_store,
    ACTION_STORE_STR: lambda raw_val: raw_val,
    ACTION_STORE_SUM: action_store_sum,
    ACTION_STORE_MIN: action_store_min, 
    ACTION_STORE_MED: action_store_med,
    ACTION_STORE_MAX: action_store_max, 
    ACTION_COUNT: action_count,
    ACTION_TRUE: lambda raw_val: raw_val not in NON_MATCH_VALUES,
    ACTION_FALSE: lambda raw_val: raw_val in NON_MATCH_VALUES,
}

MATCH_FIRST = 'first'
MATCH_LAST = 'last'
MATCH_ALL = 'all'
MATCH_UNIQ = 'uniq'
MATCH_CHOICES = {
    MATCH_FIRST: 0,
    MATCH_LAST: -1,
    MATCH_ALL: None,
    MATCH_UNIQ: None,
}


# Per file callbacks.
# These should take a results dict, key string (which may list multiple
# keys), per_file values dict, and an action callable.
# In general, they'll choose one or more of the per-file results
# to store in the results dict at the given key/s.
# They should return a list of errors/warnings.
def per_first(results: dict, key: str, file_vals: Dict[Path, Any],
              action: Callable):
    """Store the first non-empty value."""

    errors = []

    vals = [action(val) for val in file_vals.values()]
    first = [val for val in vals if val not in EMPTY_VALUES][:1]
    # Grab the first value, even if it is empty.
    if not first:
        first = vals[:1]

    if not first:
        errors.append(
            "No matches for key '{}' for any of these found files: {}."
            .format(key, ','.join(f.name for f in file_vals.keys())))
    else:
        errors.extend(store_values(results, key, first[0]))
    return errors


def per_last(results: dict, key: str, file_vals: Dict[Path, Any],
             action: Callable):
    """Store the last non-empty value."""

    errors = []

    vals = [action(val) for val in file_vals.values()]
    last = [val for val in vals if val not in EMPTY_VALUES][-1:]
    if not last:
        last = vals[-1:]
    if last is None:
        errors.append(
            "No matches for key '{}' for any of these found files: {}."
            .format(key, ','.join(f.name for f in file_vals.keys())))

    errors.extend(store_values(results, key, last))
    return errors


def per_name(results: dict, key: str, file_vals: Dict[Path, Any],
             action: Callable):
    """Store in a dict by file fullname."""

    per_file = results['per_file']
    errors = []
    normalized = {}

    for file, val in file_vals.items():
        name = normalize_filename(file)
        normalized[name] = normalized.get(name, []) + [file]
        per_file[name] = per_file.get(name, {})

        errors.extend(store_values(per_file[name], key, action(val)))

    for name, files in normalized.items():
        if len(files) > 1:
            errors.append(
                "When storing value for key '{}' per 'name', "
                "multiple files normalized to the name '{}': {}"
                .format(key, name, ', '.join([f.name for f in files])))

    return errors


def per_name_list(results: dict, key: str, file_vals: Dict[Path, Any],
                  action):
    """Store the file name for each file with a match. The action is ignored,
    and the key is expected to be a single value."""

    _ = action

    matches = []
    normalized = {}

    for file, val in file_vals.items():
        name = normalize_filename(file)
        normalized[name] = normalized.get(name, []) + [file]

        if val not in NON_MATCH_VALUES:
            matches.append(name)

    results[key] = matches

    errors = []
    for name, files in normalized.items():
        if len(files) > 1:
            errors.append(
                "When storing value for key '{}' per 'name_list', "
                "multiple files normalized to the name '{}': {}"
                .format(key, name, ', '.join([f.name for f in files])))
    return errors


def per_list(results: dict, key: str, file_vals: Dict[Path, Any],
             action: Callable):
    """Merge all values from all files into a single list. If the values
    are lists, they will be merged and the action will be applied to each
    sub-item. Single valued keys only."""

    all_vals = []
    for _, val in file_vals.items():
        val = action(val)

        if isinstance(val, list):
            all_vals.extend(val)
        else:
            all_vals.append(val)

    return store_values(results, key, all_vals)


def per_any(results: dict, key: str, file_vals: Dict[Path, Any], action):
    """Set True (single valued keys only) if any file had a match. The
    action is ignored."""

    _ = action

    results[key] = any(action(val) not in NON_MATCH_VALUES
                       for val in file_vals.values())

    return []


def per_all(results: dict, key: str, file_vals: Dict[Path, Any], action):
    """Set True (single valued keys only) if any file had a match. The
    action is ignored."""

    _ = action

    results[key] = all(action(val) not in NON_MATCH_VALUES
                       for val in file_vals.values())

    return []


PER_FIRST = 'first'
PER_LAST = 'last'
PER_NAME = 'name'
PER_NAME_LIST = 'name_list'
PER_LIST = 'list'
PER_ALL = 'all'
PER_ANY = 'any'

PER_FILES = {
    PER_FIRST: per_first,
    PER_LAST: per_last,
    PER_NAME: per_name,
    PER_NAME_LIST: per_name_list,
    PER_LIST: per_list,
    PER_ALL: per_all,
    PER_ANY: per_any,
}
