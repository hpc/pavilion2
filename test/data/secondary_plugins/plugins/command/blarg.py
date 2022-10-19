from pavilion import commands


class Blarg(commands.Command):
    def __init__(self):

        super().__init__('blarg', 'Goes Blarg!')

    def run(self, pav_cfg, args):
        pass
