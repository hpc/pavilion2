from pavilion import commands


class Bop(commands.Command):
    def __init__(self):

        super().__init__('bop', 'Goes bop!')

    def run(self, pav_cfg, args):
        pass

