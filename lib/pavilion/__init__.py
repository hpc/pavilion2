"""Perform basic module initialization tasks."""

from .schedulers.config import ScheduleConfig as _ScheduleConfig
from .test_config import TestConfigLoader as _TestConfigLoader

# This only needs to be done once, and module load time is a reasonable time for it.
_TestConfigLoader.set_sched_config(_ScheduleConfig)
