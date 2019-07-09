import sys
from pavilion import commands


class Bop(commands.Command):
    def __init__(self):

        super().__init__('bop', 'Goes bop!')

    def run(self, pav_cfg, args, out_file=sys.stdout, err_file=sys.stderr):
        pass

