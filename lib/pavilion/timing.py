"""Functions and objects related to controlling the timing of code execution."""

import time
import math
from typing import Callable, Tuple, Any, Optional

from pavilion.micro import set_default


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
