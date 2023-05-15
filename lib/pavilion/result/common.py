"""Common constants and bits for all of result handling."""
from pathlib import Path
from typing import Any

NON_MATCH_VALUES = (None, [], False)
"""Result Parser return values that are not considered to be a match."""

EMPTY_VALUES = (None, [])
"""Result Parser return values that are considered to be empty of value."""


def normalize_filename(name: Path) -> str:
    """Remove any characters that aren't allowed in Pavilion
    result variable names."""

    name = name.name.lower().split('.')[0]

    parts = []
    for part in name:
        if not part.isalnum():
            parts.append('_')
        else:
            parts.append(part)
    return ''.join(parts)


def normalize_key(key: Any):
    """Normalize the given key for use as a result key value."""
