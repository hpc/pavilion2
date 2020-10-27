"""Common constants and bits for all of result handling."""
from pathlib import Path
from pavilion import utils
from typing import Any

NON_MATCH_VALUES = (None, [], False)
"""Result Parser return values that are not considered to be a match."""

EMPTY_VALUES = (None, [])
"""Result Parser return values that are considered to be empty of value."""


class ResultError(RuntimeError):
    """Error thrown when a failure occurs with any sort of result
    processing."""


def normalize_filename(name: Path) -> str:
    """Remove any characters that aren't allowed in Pavilion
    result variable names."""

    name = name.name.lower().split('.')[0]

    parts = []
    for p in name:
        if not p.isalnum():
            parts.append('_')
        else:
            parts.append(p)
    return ''.join(parts)


def normalize_key(key: Any):
    """Normalize the given key for use as a result key value."""
