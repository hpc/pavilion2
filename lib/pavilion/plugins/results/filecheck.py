import glob

import yaml_config as yc
from pavilion.result import parsers


class Filecheck(parsers.ResultParser):
    """Checks the working directory for a given file.
    The parser will tell the user if the filename exists or not. """

    def __init__(self):
        super().__init__(
            name='filecheck',
            description="Checks working directory for a given file. Globs are"
                        "accepted.",
            config_elems=[],
        )

    def check_args(self, **kwargs) -> dict:
        """This should always have match_select set to 'first'."""

    def __call__(self, file, filename=None):
        """Simply return True. The file exists if this is called."""
        return True
