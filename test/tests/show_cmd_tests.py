import io
import json
import subprocess

from itertools import combinations

from pavilion import unittest
from pavilion import arguments
from pavilion import plugins
from pavilion import commands
from pavilion import config


class ShowTests(unittest.PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.link_files(
            "suites/hello_world.yaml",
            "platforms/that.yaml",
            "hosts/this.yaml",
            "modes/defaulted.yaml",
            "series/*",
            "collections/*",
            "plugins/schedulers/dummy.*",
            "plugins/module/*")

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

    def test_config_subcommand_aliases(self):
        """Test that the aliases for the config subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("config", "conf")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_config_dirs_subcommand(self):
        """Test that the config_dirs subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "config_dirs"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show config_dirs terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show config_dirs gave empty output")

    def test_config_dirs_subcommand_format_argument(self):
        """Test that the config_dirs subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "config_dirs", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show config_dirs --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show config_dirs --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_config_dirs_subcommand_aliases(self):
        """Test that the aliases for the config_dirs subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("config_dirs", "config_dir")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_collections_subcommand(self):
        """Test that the collections subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "collections"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show collections terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show collections gave empty output")

    def test_collections_subcommand_format_argument(self):
        """Test that the collections subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "collections", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show collections --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show collections --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_collections_subcommand_aliases(self):
        """Test that the aliases for the collections subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("collections", "collection")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

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

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show functions --detail nonexistant should have written a message to stderr, but did not.')

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

        cmd = ("show", "functions", "--format", "json", "--detail", "int")

        with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: ('--format json', '--detail int')"):
            args = parser.parse_args(cmd)

    def test_functions_subcommand_aliases(self):
        """Test that the aliases for the functions subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("functions", "functions", "func")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_platforms_subcommand(self):
        """Test that the platforms subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
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

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show platforms --config that failed with the following output:\n{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show platforms --config that gave empty output")

    def test_platforms_subcommand_mutual_exclusion(self):
        """Test that the platforms subcommand correctly disallows certain combinations of
        arguments.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        mutex_sets = [
            ("--config that", "--err", "--vars", "--verbose"),
            ("--format json", "--config that")
        ]

        for mutex_args in mutex_sets:
            for combo in combinations(mutex_args, r=2):
                cmd = ["show", "platforms"] + list(combo)

                with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: {combo}"):
                    args = parser.parse_args(cmd)

    def test_platforms_subcommand_config_argument_nonexistant(self):
        """Test that the platforms subcommand --config argument does not raise an exception when
        passed a non-existant platform."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--config", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show platforms --config nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show platforms --config nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show platforms --config nonexistant should have written a message to stderr, but did not.')

    def test_platforms_subcommand_verbose_argument(self):
        """Test that the platforms subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
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


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
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

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
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


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
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

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show platforms --vars that terminated with the following output:\n{show_cmd.errfile.getvalue()}')

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

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show platforms --vars nonexistant should have written a message to stderr, but did not.')

    def test_platforms_subcommand_vars_format(self):
        """Test that the platforms subcommand --vars argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "platforms", "--vars", "that", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show platforms --vars that --format json failed with the following output:\n{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show platforms --vars that --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_platforms_subcommand_aliases(self):
        """Test that the aliases for the platforms subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("platforms", "platform")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_hosts_subcommand(self):
        """Test that the hosts subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show hosts gave empty output")

    def test_hosts_subcommand_format_argument(self):
        """Test that the hosts subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show hosts --format json did not produce valid JSON. Output\n{output}")

    def test_hosts_subcommand_config_argument(self):
        """Test that the hosts subcommand works as expected when the --config argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--config", "this"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --config this terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show hosts --config this gave empty output")

    def test_hosts_subcommand_mutual_exclusion(self):
        """Test that the hosts subcommand correctly disallows certain combinations of
        arguments.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        mutex_sets = [
            ("--config this", "--err", "--vars", "--verbose"),
            ("--format json", "--config this")
        ]

        for mutex_args in mutex_sets:
            for combo in combinations(mutex_args, r=2):
                cmd = ["show", "hosts"] + list(combo)

                with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: {combo}"):
                    args = parser.parse_args(cmd)

    def test_hosts_subcommand_config_argument_nonexistant(self):
        """Test that the hosts subcommand --config argument does not raise an exception when
        passed a non-existant platform."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--config", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show hosts --config nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show hosts --config nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show hosts --config nonexistant should have written a message to stderr, but did not.')

    def test_hosts_subcommand_verbose_argument(self):
        """Test that the hosts subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show hosts --verbose gave empty output")

    def test_hosts_subcommand_verbose_format(self):
        """Test that the hosts subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show hosts --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_hosts_subcommand_vars_argument(self):
        """Test that the hosts subcommand --vars argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--vars", "this"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --vars this terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show hosts --vars this gave empty output")

    def test_hosts_subcommand_vars_argument_nonexistant(self):
        """Test that the hosts subcommand --vars argument does not raise an exception when
        passed a non-existant host."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--vars", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show hosts --vars nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show hosts --vars nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show hosts --vars nonexistant should have written a message to stderr, but did not.')

    def test_hosts_subcommand_vars_format(self):
        """Test that the hosts subcommand --vars argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--vars", "this", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --vars this --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show hosts --vars this --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_hosts_subcommand_err_argument(self):
        """Test that the hosts subcommand --err argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--err"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --err terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show hosts --err gave empty output")

    def test_hosts_subcommand_err_format(self):
        """Test that the hosts subcommand --err argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "hosts", "--err", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show hosts --err --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show hosts --err --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_hosts_subcommand_aliases(self):
        """Test that the aliases for the hosts subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("hosts", "host")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_modes_subcommand(self):
        """Test that the modes subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show modes terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show modes gave empty output")

    def test_modes_subcommand_format_argument(self):
        """Test that the modes subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show modes --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show modes --format json did not produce valid JSON. Output\n{output}")

    def test_modes_subcommand_config_argument(self):
        """Test that the modes subcommand works as expected when the --config argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--config", "defaulted"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show modes --config defaulted failed with the following output:\n{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show modes --config defaulted gave empty output")

    def test_modes_subcommand_mutual_exclusion(self):
        """Test that the modes subcommand correctly disallows certain combinations of
        arguments.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        mutex_sets = [
            ("--config that", "--err", "--vars", "--verbose"),
            ("--format json", "--config that")
        ]

        for mutex_args in mutex_sets:
            for combo in combinations(mutex_args, r=2):
                cmd = ["show", "modes"] + list(combo)

                with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: {combo}"):
                    args = parser.parse_args(cmd)

    def test_modes_subcommand_config_argument_nonexistant(self):
        """Test that the modes subcommand --config argument does not raise an exception when
        passed a non-existant platform."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--config", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show modes --config nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show modes --config nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show modes --config nonexistant should have written a message to stderr, but did not.')

    def test_modes_subcommand_verbose_argument(self):
        """Test that the modes subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show modes --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show modes --verbose gave empty output")

    def test_modes_subcommand_verbose_format(self):
        """Test that the modes subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show modes --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show modes --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_modes_subcommand_vars_argument(self):
        """Test that the modes subcommand --vars argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--vars", "defaulted"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show modes --vars defaulted failed with the following output:\n{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show modes --vars defaulted gave empty output")

    def test_modes_subcommand_vars_argument_nonexistant(self):
        """Test that the modes subcommand --vars argument does not raise an exception when
        passed a non-existant host."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--vars", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show modes --vars nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show modes --vars nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show modes --vars nonexistant should have written a message to stderr, but did not.')

    def test_modes_subcommand_vars_format(self):
        """Test that the modes subcommand --vars argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--vars", "defaulted", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show modes --vars defaulted --format json failed with the following output:\n{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show modes --vars defaulted --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_modes_subcommand_err_argument(self):
        """Test that the modes subcommand --err argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--err"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show modes --err terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show modes --err gave empty output")

    def test_modes_subcommand_err_format(self):
        """Test that the modes subcommand --err argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "modes", "--err", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show modes --err --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show modes --err --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_modes_subcommand_aliases(self):
        """Test that the aliases for the modes subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("modes", "mode")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_module_wrappers_subcommand(self):
        """Test that the module_wrappers subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "module_wrappers"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show module_wrappers terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show module_wrappers gave empty output")

    def test_module_wrappers_format_argument(self):
        """Test that the module_wrappers subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "module_wrappers", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show module_wrappers --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show module_wrappers --format json did not produce valid JSON. Output\n{output}")

    def test_module_wrappers_subcommand_verbose_argument(self):
        """Test that the module_wrappers subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "module_wrappers", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show module_wrappers --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show module_wrappers --verbose gave empty output")

    def test_module_wrappers_subcommand_verbose_format(self):
        """Test that the module_wrappers subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "module_wrappers", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show module_wrappers --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show module_wrappers --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_module_wrappers_subcommand_aliases(self):
        """Test that the aliases for the module_wrappers subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("module_wrappers", "module_wrapper", "mod", "modules", "module", "wrappers", "wrapper")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_nodes_subcommand(self):
        """Test that the nodes subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "nodes", "dummy"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show nodes dummy terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show nodes dummy gave empty output")

    def test_nodes_subcommand_format_argument(self):
        """Test that the nodes subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "nodes", "dummy", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show nodes dummy --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show nodes dummy --format json did not produce valid JSON. Output\n{output}")

    def test_nodes_subcommand_show_filtered_argument(self):
        """Test that the module_wrappers subcommand --show-filtered argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "nodes", "dummy", "--show-filtered"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show nodes dummy --show-filtered terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show nodes dummy --show-filtered gave empty output")

    def test_nodes_subcommand_show_filtered_format(self):
        """Test that the nodes subcommand --show-filtered argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "nodes", "dummy", "--show-filtered", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show nodes dummy --show-filtered --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show nodes dummy --show-filtered --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_nodes_subcommand_aliases(self):
        """Test that the aliases for the nodes subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("nodes", "node")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias, "dummy"))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_pavilion_variables_subcommand(self):
        """Test that the pavilion_variables subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "pavilion_variables"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show pavilion_variables terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show pavilion_variables gave empty output")

    def test_pavilion_variables_subcommand_format_argument(self):
        """Test that the pavilion_variables subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "pavilion_variables", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show pavilion_variables --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show pavilion_variables --format json did not produce valid JSON. Output\n{output}")

    def test_pavilion_variables_subcommand_aliases(self):
        """Test that the aliases for the pavilion_variables subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("pavilion_variables", "pavilion_variable", "pav_vars", "pav_vars", "pav")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_result_parsers_subcommand(self):
        """Test that the result_parsers subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show result_parsers gave empty output")

    def test_result_parsers_subcommand_format_argument(self):
        """Test that the result_parsers subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show result_parsers --format json did not produce valid JSON. Output\n{output}")

    def test_result_parsers_subcommand_list_argument(self):
        """Test that the result_parsers subcommand --list argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--list"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers --list terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show result_parsers --list gave empty output")

    def test_result_parsers_subcommand_list_format(self):
        """Test that the modes subcommand --list argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--list", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers --list --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show result_parsers --list --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_result_parsers_subcommand_doc_argument(self):
        """Test that the modes subcommand --doc argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--doc", "regex"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers --doc regex terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show result_parsers --doc regex gave empty output")

    def test_result_parsers_subcommand_doc_argument_nonexistant(self):
        """Test that the result_parsers subcommand --doc argument does not raise an exception when
        passed a non-existant result parser."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--doc", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show result_parsers --doc nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show result_parsers --doc nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show result_parsers --doc nonexistant should have written a message to stderr, but did not.')

    def test_result_parsers_subcommand_mutual_exclusion(self):
        """Test that the platforms subcommand correctly disallows certain combinations of
        arguments.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        mutex_sets = [
            ("--list", "--doc regex", "--verbose"),
            ("--format json", "--doc regex")
        ]

        for mutex_args in mutex_sets:
            for combo in combinations(mutex_args, r=2):
                cmd = ["show", "result_parsers"] + list(combo)

                with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: {combo}"):
                    args = parser.parse_args(cmd)

    def test_result_parsers_subcommand_verbose_argument(self):
        """Test that the result_parsers subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show result_parsers --verbose gave empty output")

    def test_result_parsers_subcommand_verbose_format(self):
        """Test that the result_parsers subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_parsers", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_parsers --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show result_parsers --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_result_parsers_subcommand_aliases(self):
        """Test that the aliases for the result_parsers subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("result_parsers", "result_parser", "parsers", "parser", "result")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_result_base_subcommand(self):
        """Test that the result_base subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_base"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_base terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show result_base gave empty output")

    def test_result_base_subcommand_format_argument(self):
        """Test that the result_base subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "result_base", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show result_base --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show result_base --format json did not produce valid JSON. Output\n{output}")

    def test_schedulers_subcommand(self):
        """Test that the schedulers subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show schedulers gave empty output")

    def test_schedulers_subcommand_format_argument(self):
        """Test that the schedulers subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show schedulers --format json did not produce valid JSON. Output\n{output}")

    def test_schedulers_subcommand_config_argument(self):
        """Test that the schedulers subcommand works as expected when the --config argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--config"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --config terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show modes --config gave empty output")

    def test_schedulers_subcommand_mutual_exclusion(self):
        """Test that the schedulers subcommand correctly disallows certain combinations of
        arguments.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        mutex_sets = [
            ("--list", "--config", "--vars", "--verbose"),
            ("--format json", "--config")
        ]

        for mutex_args in mutex_sets:
            for combo in combinations(mutex_args, r=2):
                cmd = ["show", "schedulers"] + list(combo)

                with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: {combo}"):
                    args = parser.parse_args(cmd)

    def test_schedulers_subcommand_verbose_argument(self):
        """Test that the schedulers subcommand --verbose argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show schedulers --verbose gave empty output")

    def test_schedulers_subcommand_verbose_format(self):
        """Test that the schedulers subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show schedulers --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_schedulers_subcommand_vars_argument(self):
        """Test that the schedulers subcommand --vars argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--vars", "dummy"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --vars dummy terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show schedulers --vars dummy gave empty output")

    def test_schedulers_subcommand_vars_argument_nonexistant(self):
        """Test that the schedulers subcommand --vars argument does not raise an exception when
        passed a non-existant host."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--vars", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show schedulers --vars nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show schedulers --vars nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show schedulers --vars nonexistant should have written a message to stderr, but did not.')

    def test_schedulers_subcommand_vars_format(self):
        """Test that the schedulers subcommand --vars argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--vars", "dummy", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --vars dummy --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show schedulers --vars dummy --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_schedulers_subcommand_list_argument(self):
        """Test that the schedulers subcommand --list argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--list"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --list terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show schedulers --list gave empty output")

    def test_schedulers_subcommand_list_format(self):
        """Test that the schedulers subcommand --list argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "schedulers", "--list", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show schedulers --list --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show schedulers --list --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_schedulers_subcommand_aliases(self):
        """Test that the aliases for the schedulers subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("schedulers", "scheduler", "sched")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_series_subcommand(self):
        """Test that the series subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show series gave empty output")

    def test_series_subcommand_format_argument(self):
        """Test that the series subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show series --format json did not produce valid JSON. Output\n{output}")

    def test_series_subcommand_path_argument(self):
        """Test that the series subcommand works as expected when the --path argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--path"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --path terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show series --path gave empty output")

    def test_series_subcommand_path_format(self):
        """Test that the series subcommand --path argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--path", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --path --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show series --path --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_series_subcommand_test_sets_argument(self):
        """Test that the series subcommand --test-sets argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--test-sets"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --test-sets terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show series --test-sets gave empty output")

    def test_series_subcommand_test_sets_format(self):
        """Test that the series subcommand --test-sets argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--test-sets", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --test-sets --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show series --test-sets --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_series_subcommand_err_argument(self):
        """Test that the series subcommand --err argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--err"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --err terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show series --err gave empty output")

    def test_series_subcommand_err_format(self):
        """Test that the series subcommand --err argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--err", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --err --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show series --err --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_series_subcommand_conflicts_argument(self):
        """Test that the series subcommand --conflicts argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--conflicts"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --conflicts terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show series --conflicts gave empty output")

    def test_series_subcommand_conflicts_format(self):
        """Test that the series subcommand --conflicts argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "series", "--conflicts", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show series --conflicts --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show series --conflicts --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_states_subcommand(self):
        """Test that the states subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "states"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show states terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show states gave empty output")

    def test_states_subcommand_format_argument(self):
        """Test that the states subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "states", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show states --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show states --format json did not produce valid JSON. Output\n{output}")

    def test_states_subcommand_aliases(self):
        """Test that the aliases for the states subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("states", "state")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_suites_subcommand(self):
        """Test that the suites subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show suites gave empty output")

    def test_suites_subcommand_format_argument(self):
        """Test that the suites subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show suites --format json did not produce valid JSON. Output\n{output}")

    def test_suites_subcommand_verbose_argument(self):
        """Test that the suites subcommand works as expected when the --verbose argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show suites --verbose gave empty output")

    def test_suites_subcommand_verbose_format(self):
        """Test that the suites subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show suites --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_suites_subcommand_err_argument(self):
        """Test that the suites subcommand --err argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--err"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --err terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show suites --err gave empty output")

    def test_suites_subcommand_err_format(self):
        """Test that the suites subcommand --err argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--err", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --err --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show suites --err --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_suites_subcommand_supersedes_argument(self):
        """Test that the suites subcommand --supersedes argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--supersedes"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --supersedes terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show suites --supersedes gave empty output")

    def test_suites_subcommand_supersedes_format(self):
        """Test that the suites subcommand --supersedes argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "suites", "--supersedes", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show suites --supersedes --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show suites --supersedes --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_suites_subcommand_aliases(self):
        """Test that the aliases for the suites subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("suites", "suite")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_system_variables_subcommand(self):
        """Test that the system_variables subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "system_variables"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show system_variables terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show system_variables gave empty output")

    def test_system_variables_subcommand_format_argument(self):
        """Test that the system_variables subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "system_variables", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show system_variables --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show system_variables --format json did not produce valid JSON. Output\n{output}")

    def test_system_variables_subcommand_verbose_argument(self):
        """Test that the system_variables subcommand works as expected when the --verbose argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "system_variables", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show system_variables --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show system_variables --verbose gave empty output")

    def test_system_variables_subcommand_verbose_format(self):
        """Test that the system_variables subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "system_variables", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show system_variables --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show system_variables --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_system_variables_subcommand_aliases(self):
        """Test that the aliases for the system_variables subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("system_variables", "system_variable", "sys_vars", "sys_var", "sys")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    def test_test_config_subcommand(self):
        """Test that the test_config subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "test_config"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show test_config terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show test_config gave empty output")

    def test_tests_subcommand(self):
        """Test that the tests subcommand, with no arguments, works as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show tests gave empty output")

    def test_tests_subcommand_format_argument(self):
        """Test that the tests subcommand --format argument behaves as expected."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--format", "json"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show tests --format json did not produce valid JSON. Output\n{output}")

    def test_tests_subcommand_verbose_argument(self):
        """Test that the tests subcommand works as expected when the --verbose argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--verbose"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --verbose terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show tests --verbose gave empty output")

    def test_tests_subcommand_verbose_format(self):
        """Test that the tests subcommand --verbose argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--verbose", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --verbose --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show tests --verbose --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_tests_subcommand_hidden_argument(self):
        """Test that the tests subcommand works as expected when the --hidden argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--hidden"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --hidden terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show tests --hidden gave empty output")

    def test_tests_subcommand_hidden_format(self):
        """Test that the tests subcommand --hidden argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--hidden", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --hidden --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show tests --hidden --format json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_tests_subcommand_err_argument(self):
        """Test that the tests subcommand works as expected when the --err argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--err"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --err terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show tests --err gave empty output")

    def test_tests_subcommand_err_format(self):
        """Test that the tests subcommand --err argument behaves as expected when the
        --format argument is also passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--err", "--format", "json"))


        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg='pav show tests --err --format json terminated with non-zero error code.')

        output = show_cmd.outfile.getvalue()

        try:
            data = json.loads(output)
        except Exception as e:
            self.fail(f"pav show tests --hidden --err json did not produce valid JSON. Output\n{output}")

        self.assertIsInstance(data, list, f"Expected JSON list.\nReceived:\n{data}")

    def test_tests_subcommand_doc_argument(self):
        """Test that the tests subcommand works as expected when the --doc argument is passed."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--doc", "hello_world.narf"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show tests --doc hello_world.narf failed with the following output\n:{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show tests --doc hello_world.narf gave empty output")

    def test_tests_subcommand_doc_argument_nonexistant(self):
        """Test that the tests subcommand --doc argument does not raise an exception when
        passed a non-existant test."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "--doc", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show tests --doc nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show tests --doc nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show tests --doc nonexistant should have written a message to stderr, but did not.')

    def test_tests_subcommand_name_filter_argument(self):
        """Test that name filtering works for the tests subcommand."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "hello*"))

        self.assertEqual(show_cmd.run(self.pav_cfg, args), 0,
                         msg=f'pav show tests hello* failed with the following output:\n{show_cmd.errfile.getvalue()}')

        output = show_cmd.outfile.getvalue()

        self.assertNotEqual(output, "", "pav show tests hello* gave empty output")

    def test_tests_subcommand_name_filter_nonexistant(self):
        """Test that the tests subcommand does not raise an exception when a name filter is
        passed that does not match any tests."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(("show", "tests", "nonexistant"))

        try:
            self.assertNotEqual(show_cmd.run(self.pav_cfg, args), 0,
                            msg='pav show tests nonexistant terminated with error code 0 despite bad input.')
        except Exception as err:
            self.fail(f"pav show tests nonexistant raised the following error:\n{err}")

        # Check that an error was printed to standard error
        error = show_cmd.errfile.getvalue()
        self.assertNotEqual(error, "", msg='pav show tests nonexistant should have written a message to stderr, but did not.')

    def test_tests_subcommand_mutual_exclusion(self):
        """Test that the tests subcommand does not allow the --doc and --format
        arguments to be passed at the same time.

        Note that this test does not test whether main.py catches the error raised by argparse."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        cmd = ("show", "tests", "--format", "json", "--doc", "hello_world.narf")

        with self.assertRaises(SystemExit, msg=f"{' '.join(cmd)} did not disallow the following combination of arguments: ('--format json', '--doc hello_world.narf')"):
            args = parser.parse_args(cmd)

    def test_tests_subcommand_aliases(self):
        """Test that the aliases for the tests subcommand work correctly."""

        parser = arguments.get_parser()

        show_cmd = commands.get_command('show')
        show_cmd.silence()

        aliases = ("tests", "test")

        for alias in aliases:
            try:
                args = parser.parse_args(("show", alias))
            except SystemExit:
                self.fail(f"Alias pav show {alias} was not recognized.")

            self.assertEqual(show_cmd.run(self.pav_cfg, args), 0, msg=f"Alias pav show {alias} was not recognized.")

    FORMATTABLE_SUBCMDS = ('config_dirs', 'collections', 'functions', 'platform', 'hosts', 'modes',
                        'module_wrappers', 'pav_vars', 'result_parsers', 'result_base',
                        'scheduler', 'states', 'sys_vars', 'suites', 'tests', 'series')

    def test_show_format_json(self):
        """Iterate over all show sub‑commands and verify JSON output."""

        parser = arguments.get_parser()
        show_cmd = commands.get_command('show')
        show_cmd.silence()

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

        for sub in self.FORMATTABLE_SUBCMDS:
            args = parser.parse_args(['show', sub, '--format', 'list'])
            ret = show_cmd.run(self.pav_cfg, args)
            self.assertEqual(ret, 0)
            output = show_cmd.outfile.getvalue()
            self.assertTrue(output.strip(), f"Expected non-empty list output for '{sub}'")
            show_cmd.outfile.truncate(0)
            show_cmd.outfile.seek(0)

    def test_show_format_list_parsable(self):
        """Test that the output from --format list is parsable by simple Linux utilities and
        that it does not output a header."""

        parser = arguments.get_parser()
        show_cmd = commands.get_command('show')
        show_cmd.silence()

        args = parser.parse_args(['show', 'schedulers', '--format', 'list'])

        ret = show_cmd.run(self.pav_cfg, args)
        self.assertEqual(ret, 0)

        output = show_cmd.outfile.getvalue()

        lines = subprocess.run(
            ["wc", "-l"],
            input=output,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True
        )

        self.assertEqual(int(lines.stdout.strip()), 4, msg=f'Expected 4 lines of output from pav show schedulers --format list. Output:\n{output}')
