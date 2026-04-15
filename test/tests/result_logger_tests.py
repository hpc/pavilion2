import json

from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase


class ResultLoggerTests(PavTestCase):

    def test_series_file_logger(self):
        """Test that the series file logger works correctly."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'results_log',
        ])

        run_cmd = commands.get_command(args.command_name)

        log_path = self.pav_cfg.working_dir / "results"
        self.pav_cfg = self.make_pav_config(result_loggers= [{
                                                "plugin": "series_file",
                                                "dest": str(log_path)}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        series = run_cmd.last_series
        series.wait_log(timeout=10)

        matches = list(log_path.glob(f"{series.id}*"))

        self.assertEqual(len(matches), 1,
                         msg=f"Expected exactly one log file matching '{series.id}*', "
                             f"but found {len(matches)}: {matches}")

        log_path = next(iter(matches))

        with open(log_path) as fin:
            results = json.load(fin)

        self.assertEqual(results.get("hello"), "world")

    def test_common_file_logger(self):
        """Test that the common file logger works correctly."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'results_log',
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        log_path = self.pav_cfg.working_dir / "results.log"
        self.pav_cfg = self.make_pav_config(result_loggers=[{
                                                "plugin": "common_file",
                                                "dest": str(log_path)}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        series1 = run_cmd.last_series

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        series2 = run_cmd.last_series

        series1.wait_log(timeout=10)
        series2.wait_log(timeout=10)

        with open(log_path) as fin:
            results = fin.readlines()

        self.assertEqual(len(results), 2)

        for res in results:
            results = json.loads(res)
            self.assertEqual(results.get("hello"), "world")

    def test_logging_process_exits_once_series_completed(self):
        """Test that the result logging process exits once the entire series has completed."""

    def test_logging_process_times_out_if_no_activity(self):
        """Test that the result logging process times out when tests are not active."""

    def test_load_custom_result_logger_plugin(self):
        """Test that custom result loggers can be loaded."""

    def test_logging_exits_if_no_loggers(self):
        """Test that the result logging process exits if there are no result loggers defined."""

    def test_logging_gracefully_handles_errors(self):
        """Test that the logging process gracefully handles ResultLoggerPluginErrors."""

    def test_series_file_result_logger_has_separate_files_for_reused_series_ids(self):
        """Test that when series IDs are used, the SeriesFileResultLogger gives them separate
        result logs."""
