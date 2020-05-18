from pathlib import Path
from pavilion.results import parsers
import yaml_config as yc


class Filecheck(parsers.ResultParser):
    """Checks the working directory for a given file.
    The parser will tell the user if the filename exists or not. """

    def __init__(self):
        super().__init__(name='filecheck',
                         description="Checks working directory"
                         "for a given file")

    def get_config_items(self):
        # Result parser consists of 1 string elem: filename.
        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'filename', required=True,
                help_text="Filename to find in working directory."
            )
        ])
        return config_items

    def __call__(self, test, file, filename):
        # recursively search folders in path for filename.
        for f in Path(test.path).rglob(filename):
            return True
        return False
