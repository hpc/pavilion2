from pavilion import commands
import sys


class Blarg(commands.Command):
    def __init__(self):

        super().__init__('blarg', 'Goes Blarg!')

    def run(self, pav_cfg, args):
        print("Blarg!")
