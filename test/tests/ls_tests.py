import io

from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase


class StatusTests(PavTestCase):

    def test_ls(self):
        """Checking ls command functionality"""
        test = self._quick_test()

        ls_cmd = commands.get_command('ls')
        ls_cmd.outfile = io.StringIO()
        ls_cmd.errfile = io.StringIO()

        arg_parser = arguments.get_parser()
        arg_sets = (
            ['ls', str(test.id)],
            ['ls', str(test.id), '--tree'],
            ['ls', str(test.id), 'build'],
        )

        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            ls_cmd.run(self.pav_cfg, args)
