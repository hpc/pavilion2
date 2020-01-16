from pathlib import Path
from pavilion import config
from pavilion import result_parsers
from pavilion import utils
import errno
import glob
import os
import sys
import yaml_config as yc


class Filecheck(result_parsers.ResultParser):
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
            yc.StrElem('filename', required=True,
                       help_text="The filename result parser"
                                 "takes in a string and checks"
                                 "the working directory for said "
                                 "file. It will return True with "
                                 " the path-to-file or False.")
        ])

        return config_items

    def _check_args(self, filename=None):
        # Filename can being anything but none.
        if not filename:
            raise result_parser.ResultParserError(
                "File name cannot be null"
            )

    def __call__(self, test, file, filename):
        # try to create config to get info on job.
        try:
            pav_cfg = config.find()
        except Exception as err:
            return errno.EEXIST

        # Build the test path of the job using make_id_path.
        working_dir = pav_cfg.working_dir/'test_runs'
        test_path = utils.make_id_path(working_dir, test.id)
        # recursively search folders in path for filename.
        for file in Path(str(test_path)).rglob(filename):
            return "File found at " + str(file)

        return "File not found."
