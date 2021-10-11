"""Split line by a substring."""

import yaml_config as yc
from pavilion.result_parsers import base_classes


class Split(base_classes.ResultParser):
    """Split a line by some substring, and return the list of parts."""

    def __init__(self):
        super().__init__(
            name='split',
            description="Split by a substring, are return the whitespace "
                        "stripped parts.",
            config_elems=[
                yc.StrElem(
                    'sep',
                    help_text="The substring to split by. Default is "
                              "to split by whitespace.")]
        )

    # pylint: disable=arguments-differ
    def __call__(self, file, sep=None):
        """Simply use the split string method to split"""

        sep = None if sep == '' else sep

        line = file.readline().strip()

        return [part.strip() for part in line.split(sep)]
