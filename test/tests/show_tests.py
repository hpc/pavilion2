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
            ('show', 'result_parsers', '--verbose'),
            ('show', 'result_parsers', '--config=regex'),
            ('show', 'states'),
            ('show', 'config'),
            ('show', 'config', '--template'),
            ('show', 'test_config'),
            ('show', 'module_wrappers'),
            ('show', 'module_wrappers', '--verbose'),
            ('show', 'system_variables'),
            ('show', 'system_variables', '--verbose'),
            ('show', 'pav_vars'),
            ('show', 'suites'),
            ('show', 'suites', '--verbose'),
            ('show', 'suites', '--err'),
            ('show', 'suites', '--supersedes'),
            ('show', 'tests'),
            ('show', 'tests', '--verbose'),
            ('show', 'tests', '--err'),
            ('show', 'hosts'),
            ('show', 'hosts', '--verbose'),
            ('show', 'modes'),
            ('show', 'modes', '--verbose'),
        ]

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.outfile = io.StringIO()
        show_cmd.errfile = io.StringIO()

        for arg_list in arg_lists:
            args = parser.parse_args(arg_list)
            show_cmd.run(self.pav_cfg, args)

        plugins._reset_plugins()
