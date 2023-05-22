"""Test the cancel command."""

import time

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import series
from pavilion.status_file import SERIES_STATES
from pavilion.unittest import PavTestCase


class SeriesCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_run_series(self):
        """Test cancel command with no arguments."""

        run_cmd: commands.RunSeries = commands.get_command('series')
        arg_parser = arguments.get_parser()

        arg_lists = [
            ['series', 'run', 'basic'],
            ['series', 'run', 'basic', '--skip-verify'],
        ]

        for arg_list in arg_lists:
            args = arg_parser.parse_args(arg_list)
            run_cmd.silence()

            run_result = run_cmd.run(self.pav_cfg, args)
            self.assertEqual(run_result, 0)

            run_cmd.last_run_series.wait()
            self.assertEqual(run_cmd.last_run_series.complete, True)
            self.assertEqual(run_cmd.last_run_series.info().passed, 1)

    def test_run_series_modes(self):
        """Make sure command line modes are applied when running series."""

        run_cmd: commands.RunSeries = commands.get_command('series')
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'series',
            'run',
            'basic',
            '-m',
            'smode1',
        ])
        run_cmd.silence()

        run_result = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        series_obj = run_cmd.last_run_series
        series_obj.wait(5)
        self.assertEqual(series_obj.complete, True)
        self.assertEqual(series_obj.info().passed, 1)

        test = list(series_obj.tests.values())[0]

        self.assertEqual(test.var_man['var.asdf'], 'asdf1')

    def test_run_series_overrides(self):
        """Make sure command line modes are applied when running series."""

        run_cmd: commands.RunSeries = commands.get_command('series')
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'series',
            'run',
            '-c',
            'variables.val="via_overrides"',
            'basic',
        ])
        run_cmd.silence()

        run_result = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        series_obj = run_cmd.last_run_series
        series_obj.wait(5)
        self.assertEqual(series_obj.complete, True)
        self.assertEqual(series_obj.info().passed, 1)

        test = list(series_obj.tests.values())[0]

        self.assertEqual(test.var_man['var.val'], 'via_overrides')


    def test_cancel_series(self):
        """Test cancel command with no arguments."""

        series_cmd: commands.RunSeries = commands.get_command('series')
        arg_parser = arguments.get_parser()

        # This series starts two tests. One that ends almost immediately an one
        # that runs (sleeps) for a while.
        args = arg_parser.parse_args([
            'series',
            'run',
            'sleepy'])
        series_cmd.silence()
        run_result = series_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        ser = series_cmd.last_run_series
        self._wait_for_all_start(ser)

        cancel_args = arg_parser.parse_args(['series', 'cancel', series_cmd.last_run_series.sid])
        cancel_result = series_cmd.run(self.pav_cfg, cancel_args)
        self.assertEqual(cancel_result, 0)
        self.assertEqual(ser.status.current().state, SERIES_STATES.CANCELED)

    def test_series_sets(self):
        """Attempt the 'series sets' command."""

        series_cmd: commands.RunSeries = commands.get_command('series')
        series_cmd.silence()
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['series', 'run', 'multi'])
        self.assertEqual(series_cmd.run(self.pav_cfg, args), 0)
        series_cmd.last_run_series.wait()
        sid = series_cmd.last_run_series.sid

        arg_lists = [
            ['series', 'sets', sid],
            ['series', 'sets', '--merge-repeats', sid],
        ]

        series_cmd.clear_output()

        for arg_list in arg_lists:
            args = arg_parser.parse_args(arg_list)

            self.assertEqual(series_cmd.run(self.pav_cfg, args), 0)

    def test_series_list(self):
        """Test the series list command."""

        series_cmd: commands.RunSeries = commands.get_command('series')
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'series',
            'run',
            'basic',
        ])
        series_cmd.silence()
        run_result = series_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        self._wait_for_all_start(series_cmd.last_run_series)

        list_args = [
            ['series', 'list'],
            ['series', 'ls', series_cmd.last_run_series.sid],
            ['series', 'status', 'all'],
        ]
        for raw_args in list_args:
            args = arg_parser.parse_args(raw_args)
            self.assertEqual(series_cmd.run(self.pav_cfg, args), 0)

    def test_series_history(self):
        """Test the series list command."""

        series_cmd: commands.RunSeries = commands.get_command('series')
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'series',
            'run',
            'basic',
        ])
        series_cmd.silence()
        run_result = series_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        self._wait_for_all_start(series_cmd.last_run_series)

        list_args = [
            ['series', 'state_history', '--text'],
            ['series', 'states', series_cmd.last_run_series.sid],
        ]
        for raw_args in list_args:
            args = arg_parser.parse_args(raw_args)
            self.assertEqual(series_cmd.run(self.pav_cfg, args), 0)

    def _wait_for_all_start(self, ser: series.TestSeries, timeout=10):
        # Wait for the series to start.
        start_time = time.time()
        while not ser.status.has_state(SERIES_STATES.ALL_STARTED):
            if time.time() - start_time > timeout:
                stat_lines = ['current time: {}'.format(time.time())]
                for stat in ser.status.history():
                    stat_lines.append(str(stat))
                self.fail("Could not detect series start. Series status: \n{}"
                          .format('\n'.join(stat_lines)))
            time.sleep(0.3)
