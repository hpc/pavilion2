"""Displays the Pavilion version."""

import errno
import re

from pavilion import commands
from pavilion import output
from pavilion.output import fprint


class VersionCommand(commands.Command):

    def __init__(self):
        super().__init__(
            name='version',
            description='Display version of Pavilion.',
            short_help="Displays the current version of Pavilion.",
        )

    def run(self, pav_cfg, args):
        """Run fetches the version number from RELEASE.txt"""

        version_path = str(pav_cfg.pav_root) + '/RELEASE.txt'

        try:
            with open(version_path, 'r') as file:
                lines = file.readlines()
                version_found = False
                for line in lines:
                    if re.search(r'RELEASE=', line):
                        version_found = True
                        fprint('Pavilion ' + line.split('=')[1])
            if not version_found:
                fprint('Pavilion version not found in RELEASE.txt', color=output.RED)

        except FileNotFoundError:
            fprint(version_path + " not found.", file=self.errfile, color=output.RED)
            return errno.ENOENT
