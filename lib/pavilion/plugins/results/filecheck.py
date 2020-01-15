from pathlib import Path
from pavilion import config
from pavilion import result_parsers
from pavilion import utils
import yaml_config as yc
import glob
import os
import sys


class Filecheck(result_parsers.ResultParser):
    """Checks the working directory for the given file name.
    The parser will tell the user if the filename exists or not. """

    def __init__(self):
        super().__init__(name='filecheck',
                         description="Checks working directory"
                         "for given file name")

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem('filename', required=True,
                       help_text="The filename result parser"
                                 "takes in a string and checks"
                                 "the working directory for said "
                                 "filename. It will return True or "
                                 "False.")
        ])

        return config_items

    def _check_args(self, filename=None):
        if filename == "" or filename is None:
            raise result_parser.ResultParserError(
                "File name cannot be null"
            )

    def __call__(self, test, file, filename):
        try:
            pav_cfg = config.find()
        except Exception as err:
            sys.exit(-1)

        working_dir = pav_cfg.working_dir/'test_runs'
        test_path = utils.make_id_path(working_dir, test.id)
        for file in Path(str(test_path)).rglob(filename):
            return "File found at " + str(file)

        return "File not found."
