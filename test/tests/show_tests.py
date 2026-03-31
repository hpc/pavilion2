import io
import json

from pavilion import unittest
from pavilion import arguments
from pavilion import plugins
from pavilion import commands
from pavilion import config


class ShowTests(unittest.PavTestCase):

    def test_config_subcommand(self):
        """Test that the config subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "config"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show config terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()
        expected = io.StringIO()
        config.PavilionConfigLoader().dump(expected, self.pav_cfg)

        self.assertEqual(output, expected.getvalue(),
                         msg='pav show config output does not match loaded Pavilion config.')

    def test_config_subcommand_template_arg(self):
        """Test that the config subcommand --template argument works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "config", "--template"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show config --template terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()
        expected = io.StringIO()
        config.PavilionConfigLoader().dump(expected)

        self.assertEqual(output, expected.getvalue(),
                         msg='Loaded Pavilion config was printed instead of the template.')

    def test_functions_subcommand(self):
        """Test that the functions subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "functions"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show functions terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show functions gave empty output")

    def test_functions_subcommand_detail_argument(self):
        """Test that the functions subcommand --detail argument works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "functions", "--detail", "int"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show functions --detail int terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show functions --detail int gave empty output")

    def test_functions_subcommand_detail_argument_nonexistant(self):
        """Test that the functions subcommand --detail argument does not raise an exception when
        passed a non-existant function."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "functions", "--detail", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show functions --detail nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show functions --detail nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard output
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "")

    def test_functions_subcommand_format_argument(self):
        """Test that the functions subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "functions", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show functions --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show functions --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_functions_subcommand_mutual_exclusion(self):
        """Test that the functions subcommand does not allow the --detail and --format
        arguments to be passed at the same time.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        with self.assertRaises(SystemExit):
            args = parser.parse_args(("show", "functions", "--format", "json", "--detail", "int"))

    def test_platforms_subcommand(self):
        """Test that the platforms subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms"))

        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show platforms gave empty output")

    def test_platforms_subcommand_format_argument(self):
        """Test that the platforms subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show platforms --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show platforms --format json did not produce valid JSON. Output\n{output}")

    def test_platforms_subcommand_config_argument(self):
        """Test that the platforms subcommand works as expected when the --config argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--config", "that"))

        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --config that terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show platforms --config that gave empty output")

    def test_platforms_subcommand_config_mutual_exclusion(self):
        """Test that the platforms subcommand does not allow the --config and --format
        arguments to be passed at the same time.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        with self.assertRaises(SystemExit):
            args = parser.parse_args(("show", "platforms", "--format", "json", "--config", "that"))

    def test_platforms_subcommand_config_argument_nonexistant(self):
        """Test that the platforms subcommand --config argument does not raise an exception when
        passed a non-existant platform."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--config", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show platforms terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show platforms --config nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard output
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "")

    def test_platforms_subcommand_verbose_argument(self):
        """Test that the platforms subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--verbose"))

        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show platforms --verbose gave empty output")

    def test_platforms_subcommand_verbose_format(self):
        """Test that the platforms subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show platforms --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_platforms_subcommand_err_argument(self):
        """Test that the platforms subcommand --err argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--err"))

        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --err terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show platforms --err gave empty output")

    def test_platforms_subcommand_err_format(self):
        """Test that the platforms subcommand --err argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--err", "--format", "json"))


        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --err --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show platforms --err --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_platforms_subcommand_vars_argument(self):
        """Test that the platforms subcommand --vars argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--vars", "that"))

        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --vars that terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show platforms --vars that gave empty output")

    def test_platforms_subcommand_vars_argument_nonexistant(self):
        """Test that the platforms subcommand --vars argument does not raise an exception when
        passed a non-existant platform."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--vars", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show platforms --vars nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show platforms --vars nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard output
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "")

    def test_platforms_subcommand_vars_format(self):
        """Test that the platforms subcommand --vars argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--vars", "that", "--format", "json"))

        self.assertEqual(show_cmd.run(self.platforms, args), 0,
                         msg='pav show platforms --vars that --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show platforms --vars that --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_show_cmds(self):

        arg_lists = [
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
