import sys
from pavilion import commands


class Poof(commands.Command):
    def __init__(self):

        super().__init__('poof', 'Goes POOF!')

    def run(self, pav_cfg, args):
        pass

