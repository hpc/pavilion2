"""
COMPATABILITY for config/sys/plugins which
    import pavilion.system_variables

DEPRECATE SOON
When all production pavilion clones are updated, update config plugins
to use sys_vars instead.
"""

from pavilion.sys_vars import *
