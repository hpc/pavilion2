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
            config_elems=[
                yc.StrElem(
                    'filename', required=True,
                    help_text="Filename to find in working directory."
                )
            ]
        )

    def __call__(self, test, file, filename=None):

        return bool(glob.glob((test.path/'build/').as_posix() + filename))
