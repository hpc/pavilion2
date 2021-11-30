"""Perform basic module initialization tasks."""

from .schedulers.config import ScheduleConfig as _ScheduleConfig
from .test_config import file_format as _file_format

# This only needs to be done once, and module load time is a reasonable time for it.

_file_format.TestConfigLoader.SCHEDULE_CLASS = _ScheduleConfig
