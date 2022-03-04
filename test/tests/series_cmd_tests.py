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

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'series',
            'run',
            'basic'
        ])
        run_cmd: commands.RunSeries = commands.get_command(args.command_name)
        run_cmd.silence()

        run_result = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        run_cmd.last_run_series.wait()
        self.assertEqual(run_cmd.last_run_series.complete, True)
        self.assertEqual(run_cmd.last_run_series.info().passed, 1)

    def test_cancel_series(self):
        """Test cancel command with no arguments."""

        arg_parser = arguments.get_parser()

        # This series starts two tests. One that ends almost immediately an one
        # that runs (sleeps) for a while.
        args = arg_parser.parse_args([
            'series',
            'run',
            'sleepy',
        ])
        series_cmd: commands.RunSeries = commands.get_command(args.command_name)
        series_cmd.silence()
        run_result = series_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        ser = series_cmd.last_run_series
        self._wait_for_all_start(ser)

        cancel_args = arg_parser.parse_args(['series', 'cancel', series_cmd.last_run_series.sid])
        cancel_result = series_cmd.run(self.pav_cfg, cancel_args)
        self.assertEqual(cancel_result, 0)
        self.assertEqual(ser.status.current().state, SERIES_STATES.CANCELED)

    def test_series_list(self):
        """Test the series list command."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'series',
            'run',
            'basic',
        ])
        series_cmd: commands.RunSeries = commands.get_command(args.command_name)
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

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'series',
            'run',
            'basic',
        ])
        series_cmd: commands.RunSeries = commands.get_command(args.command_name)
        series_cmd.silence()
        run_result = series_cmd.run(self.pav_cfg, args)
        self.assertEqual(run_result, 0)

        self._wait_for_all_start(series_cmd.last_run_series)

        list_args = [
            ['series', 'history', '--text'],
            ['series', 'history', series_cmd.last_run_series.sid],
        ]
        for raw_args in list_args:
            args = arg_parser.parse_args(raw_args)
            self.assertEqual(series_cmd.run(self.pav_cfg, args), 0)

    def _wait_for_all_start(self, ser: series.TestSeries, timeout=30):
        # Wait for the series to start.
        start_time = time.time()
        while not ser.status.has_state(SERIES_STATES.ALL_STARTED):
            if time.time() - start_time > timeout:
                stat_lines = ['current time: {}'.format(time.time())]
                for stat in ser.status.history():
                    stat_lines.append(str(stat))
                with (ser.path/'series.out').open() as out:
                    print(out.read())
                self.fail("Could not detect series start. Series status: \n{}"
                          .format('\n'.join(stat_lines)))
            time.sleep(0.3)
