
from pavilion import commands


class GraphCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'graph',
            'Command used to produce graph for a group of tests.',
            short_help="Produce graph for tests."
        )

    def run(self, pav_cfg, args):

        print("GRAPHING....")
