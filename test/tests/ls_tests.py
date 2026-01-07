import io

from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase


class LsTests(PavTestCase):

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
            ['ls', str(test.id), '--path'],
            ['ls', str(test.id), '--perms'],
            ['ls', str(test.id), '--size'],
            ['ls', str(test.id), '--date'],
            ['ls', str(test.id), '--symlink'],
            ['ls', str(test.id), '--long'],
            ['ls', str(test.id), 'build'],
        )

        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            self.assertEqual(ls_cmd.run(self.pav_cfg, args), 0)

    def test_ls_last_test(self):
        """Test that ls automatically finds the last test when no test ID is given."""

        ls_cmd = commands.get_command('ls')
        ls_cmd.silence()

        run_cmd = commands.get_command("run")
        run_cmd.silence()

        parser = arguments.get_parser()
        ls_args = parser.parse_args(["ls"])

        run_args = ["run", "-H", "this", "hello_world.hello"]
        run_cmd.run(self.pav_cfg, parser.parse_args(run_args))

        self.assertEqual(ls_cmd.run(self.pav_cfg, ls_args), 0)

    def test_ls_nonexistent_test(self):
        """Test that ls behaves correctly when the specified test doesn't exist."""

        ls_cmd = commands.get_command('ls')
        ls_cmd.silence()

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args(["ls", "s9000.1"])

        self.assertEqual(ls_cmd.run(self.pav_cfg, args), 2)