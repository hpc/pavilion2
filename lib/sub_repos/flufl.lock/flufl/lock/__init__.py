# Adapted from: flufl.lock/__init__.py (https://gitlab.com/warsaw/flufl.lock/-/tree/6.0)
# Copyright 2021 Barry Warsaw
# Modifications Copyright 2026 Los Alamos National Laboratory
# Licensed under the Apache License, Version 2.0
#
# Modifications:
# - Adapted to remove dependency on `public` package (2026, Hank Wikle, Los Alamos National Laboratory)
# - Removed custom `TimeOutError` in favor of native Python `TimeoutError` (2026, Hank Wikle, Los Alamos National Laboratory)
#
# Original license text is included in LICENSE file.


from flufl.lock._lockfile import (
    AlreadyLockedError,
    Lock,
    LockError,
    LockState,
    NotLockedError,
    SEP,
)


__version__ = '6.0'
