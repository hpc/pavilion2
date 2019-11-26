from pavilion import unittest
from pavilion import arguments
from pavilion import plugins
from pavilion import commands
import io


class ShowTests(unittest.PavTestCase):

    def test_show_cmds(self):

        plugins.initialize_plugins(self.pav_cfg)

        arg_lists = [
            ('show', 'sched'),
            ('show', 'sched', '--config=slurm'),
            ('show', 'sched', '--vars=slurm'),
            ('show', 'result_parsers'),
            ('show', 'result_parsers', ),
        ]

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.outfile = io.StringIO()
        show_cmd.errfile = io.StringIO()

        for arg_list in arg_lists:
            args = parser.parse_args(arg_list)
            show_cmd.run(self.pav_cfg, args)

        plugins._reset_plugins()


