from pavilion import unittest
from pavilion import arguments
from pavilion import plugins
from pavilion import commands
import io
import json


class ShowTests(unittest.PavTestCase):

    def test_show_cmds(self):

        arg_lists = [
            ('show', 'config'),
            ('show', 'config', '--template'),
            ('show', 'functions'),
            ('show', 'functions', '--detail', 'int'),
            ('show', 'platform'),
            ('show', 'platform', '--verbose'),
            ('show', 'platform', '--vars', 'that'),
            ('show', 'platform', '--config', 'that'),
            ('show', 'hosts'),
            ('show', 'hosts', '--verbose'),
            ('show', 'hosts', '--vars', 'this'),
            ('show', 'hosts', '--config', 'this'),
            ('show', 'modes'),
            ('show', 'modes', '--verbose'),
            ('show', 'modes', '--vars', 'defaulted'),
            ('show', 'modes', '--config', 'defaulted'),
            ('show', 'module_wrappers'),
            ('show', 'module_wrappers', '--verbose'),
            ('show', 'pav_vars'),
            ('show', 'result_parsers'),
            ('show', 'result_parsers', '--doc=regex'),
            ('show', 'result_parsers', '--verbose'),
            ('show', 'sched'),
            ('show', 'sched', '--config'),
            ('show', 'sched', '--vars=slurm'),
            ('show', 'states'),
            ('show', 'suites'),
            ('show', 'suites', '--err'),
            ('show', 'suites', '--supersedes'),
            ('show', 'suites', '--verbose'),
            ('show', 'system_variables'),
            ('show', 'system_variables', '--verbose'),
            ('show', 'test_config'),
            ('show', 'tests'),
            ('show', 'tests', 'name_filter'),
            ('show', 'tests', '--err'),
            ('show', 'tests', '--doc', 'hello_world.narf'),
            ('show', 'tests', '--hidden'),
            ('show', 'tests', '--verbose'),
        ]

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        for arg_list in arg_lists:
            args = parser.parse_args(arg_list)
            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0)

    FORMATTABLE_SUBCMDS = ('config_dirs', 'collections', 'functions', 'platform', 'hosts', 'modes',
                        'module_wrappers', 'pav_vars', 'result_parsers', 'result_base',
                        'scheduler', 'states', 'sys_vars', 'suites', 'tests', 'series')

    def test_show_format_json(self):
        """Iterate over all show sub‑commands and verify JSON output."""

        parser = arguments.get_parser()
        show_cmd = commands.get_command('show')
        show_cmd.silence()

        # Capture output
        show_cmd.outfile = io.StringIO()

        for sub in self.FORMATTABLE_SUBCMDS:
            args = parser.parse_args(['show', sub, '--format', 'json'])
            ret = show_cmd.run(self.pav_cfg, args)

            self.assertEqual(ret, 0)

            output = show_cmd.outfile.getvalue()

            try:
                data = json.loads(output)
            except Exception as e:
                self.fail(f"JSON parsing failed for subcommand '{sub}'.\nOutput:\n{output}\n{e}")

            self.assertIsInstance(data, list, f"Expected JSON list for '{sub}'.\nData:\n{data}")

            # Reset for next iteration
            show_cmd.outfile.truncate(0)
            show_cmd.outfile.seek(0)

    def test_show_format_table(self):
        """Iterate over all show sub‑commands and verify table output."""

        parser = arguments.get_parser()
        show_cmd = commands.get_command('show')
        show_cmd.silence()
        show_cmd.outfile = io.StringIO()

        for sub in self.FORMATTABLE_SUBCMDS:
            args = parser.parse_args(['show', sub, '--format', 'table'])
            ret = show_cmd.run(self.pav_cfg, args)
            self.assertEqual(ret, 0)
            output = show_cmd.outfile.getvalue()
            self.assertTrue(output.strip(), f"Expected non-empty table output for '{sub}'")
            show_cmd.outfile.truncate(0)
            show_cmd.outfile.seek(0)

    def test_show_format_list(self):
        """Iterate over all show sub‑commands and verify list output."""
        subcommands = [
            'config', 'config_dirs', 'collections', 'functions',
            'platform', 'hosts', 'modes', 'module_wrappers',
            'pav_vars', 'result_parsers', 'result_base',
            'schedulers', 'states', 'sys_vars', 'suites',
            'tests', 'series', 'test_config'
        ]

        parser = arguments.get_parser()
        show_cmd = commands.get_command('show')
        show_cmd.silence()
        show_cmd.outfile = io.StringIO()

        for sub in self.FORMATTABLE_SUBCMDS:
            args = parser.parse_args(['show', sub, '--format', 'list'])
            ret = show_cmd.run(self.pav_cfg, args)
            self.assertEqual(ret, 0)
            output = show_cmd.outfile.getvalue()
            self.assertTrue(output.strip(), f"Expected non-empty list output for '{sub}'")
            show_cmd.outfile.truncate(0)
            show_cmd.outfile.seek(0)
