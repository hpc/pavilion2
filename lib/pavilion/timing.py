"""Functions and objects related to controlling the timing of code execution."""

import time
import math
from pathlib import Path
from typing import Callable, Tuple, Any, Optional

from pavilion.micro import set_default
from pavilion.path_utils import Pathlike


class RateLimiter:
    """Wraps a call to a function and only calls it if the specified
    cooldown (in seconds) has elapsed since the last call."""

    def __init__(self, func: Callable[[], Any], cooldown: float):
        self.function = func
        self.cooldown = cooldown
        self.last_called = -math.inf

    def __call__(self) -> Tuple[bool, Any]:
        """Calls the function if enough time has passed, and returns
        a tuple containing a boolean indicating whether the function was actually called
        and the return value of the function (or None if it was not called)."""

        current_time = time.time()

        if current_time - self.last_called > self.cooldown:
            res = self.function()
            self.last_called = current_time

            return (True, res)

        return (False, None)


def wait(cond: Callable[[], bool], interval: float, timeout: Optional[float] = None,
         msg: Optional[str] = None, cond_name: Optional[str] = None) -> None:
    """Waits until the given condition becomes true before continuing execution,
    optionally timing out after the given duration."""

    cond_name = set_default(cond_name, cond.__name__)

    timeout = set_default(timeout, math.inf)
    msg = set_default(
                msg,
                f"Timeout exceeded while waiting for condition \"{cond_name}\" to become true"
                )

    start_time = time.time()

    while time.time() - start_time < timeout:
        if cond():
            return

        time.sleep(interval)

    raise TimeoutError(msg)


class AbsoluteDeadlineTimeout:
    """NFS-safe timeout strategy using absolute deadlines.

    This class implements a timeout algorithm that is robust against stale
    NFS metadata caching. It maintains an absolute deadline that can only
    move forward (be extended), never backward, making it safe when file
    modification times are cached and potentially stale.

    When a file is modified, the deadline is extended. When file metadata
    is stale (from cache), the existing deadline is preserved. This ensures
    that stale metadata cannot cause premature timeouts.
    """

    def __init__(self, timeout_file: Pathlike, timeout_period: Optional[float] = None):
        """Initialize the timeout strategy.

        :param timeout_file: Path to file whose modification time indicates activity
        :type timeout_file: Pathlike
        :param timeout_period: Timeout duration in seconds, or None for no timeout
        :type timeout_period: Optional[float]
        """
        self.timeout_file = Path(timeout_file)
        self.timeout_period = set_default(timeout_period, math.inf)
        self.deadline = time.time() + self.timeout_period

    def remaining_time(self, timeout_file: Pathlike) -> float:
        """Calculate remaining time until timeout deadline.

        Updates the internal deadline based on the timeout file's modification
        time. If the file has been modified recently, the deadline is extended.
        The deadline can only move forward (extended), never backward, which
        makes this algorithm safe against stale NFS metadata caching.

        If an OSError occurs while checking the file (e.g., file doesn't exist,
        permission denied, network error), the current deadline is preserved.

        :return: Remaining seconds until timeout. Returns math.inf if no timeout
                 is configured. Returns negative value if timeout has been exceeded.
        :rtype: float
        """
        try:
            file_mtime = timeout_file.stat().st_mtime
            # Extend deadline if file was modified recently (deadline can only move forward)
            self.deadline = max(self.deadline, file_mtime + self.timeout_period)
        except OSError:
            # If we can't stat the file, keep the existing deadline
            pass

        # Calculate and return remaining time (may be negative if exceeded)
        return self.deadline - time.time()

