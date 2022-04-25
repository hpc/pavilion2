"""Built in Result Parser plugins live here. While they're plugins, they're added
manually for speed."""

from .base_classes import (ResultParser, ResultError, get_plugin, list_plugins,
                           match_pos_validator, match_select_validator)

from .command import Command
from .constant import Constant
from .filecheck import Filecheck
from .json import Json
from .regex import Regex
from .split import Split
from .table import Table

_builtin_result_parsers = [
    Command,
    Constant,
    Filecheck,
    Json,
    Regex,
    Split,
    Table,
]


def register_core_plugins():
    """Add all builtin plugins and activate them."""

    for cls in _builtin_result_parsers:
        obj = cls()
        obj.activate()


ResultParser.register_core_plugins = register_core_plugins
