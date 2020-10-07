"""Return a constant."""

import yaml_config as yc
from pavilion.result import parsers


class Constant(parsers.ResultParser):
    """Set a constant as result."""

    def __init__(self):
        super().__init__(
            name='constant',
            description="Insert a constant (can contain Pavilion variables) "
                        "into the results.",
            config_elems=[
                yc.StrElem(
                    'const', required=True,
                    help_text="Constant that will be placed in result."
                )
            ]
        )

    def __call__(self, test, file, const=None):
        return const
