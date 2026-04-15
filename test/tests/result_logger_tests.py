import json
import io

from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion.result_logging import get_result_loggers


class ResultLoggerTests(PavTestCase):

    def test_series_file_logger(self):
        """Test that the series file logger works correctly."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        log_path = self.pav_cfg.working_dir / "results"
        self.pav_cfg = self.make_pav_config(result_loggers= [{
                                                "plugin": "series_file",
                                                "dest": str(log_path)}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")

        series = run_cmd.last_series

        try:
            series.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series.id} to finish logging results after 10 seconds.")

        matches = list(log_path.glob(f"{series.id}*"))

        self.assertEqual(len(matches), 1,
                         msg=f"Expected exactly one log file matching '{series.id}*', "
                             f"but found {len(matches)}: {matches}")

        log_path = next(iter(matches))

        try:
            with open(log_path) as fin:
                results = json.load(fin)
        except FileNotFoundError:
            self.fail(f"Results log at {log_path} was never created.")
        except OSError:
            self.fail(f"Could not read results log at {log_path}.")

        self.assertEqual(results.get("hello"), "world")

    def test_common_file_logger(self):
        """Test that the common file logger works correctly."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        log_path = self.pav_cfg.working_dir / "results.log"
        self.pav_cfg = self.make_pav_config(result_loggers=[{
                                                "plugin": "common_file",
                                                "dest": str(log_path)}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")
        series1 = run_cmd.last_series

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")
        series2 = run_cmd.last_series

        try:
            series1.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series1.id} to finish logging results after 10 seconds.")

        try:
            series2.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series2.id} to finish logging results after 10 seconds.")

        try:
            with open(log_path) as fin:
                results = fin.readlines()
        except FileNotFoundError:
            self.fail(f"Results log at {log_path} was never created.")
        except OSError:
            self.fail(f"Could not read results log at {log_path}.")

        self.assertEqual(len(results), 2,
                         msg=f"Expected exactly 2 results to be written to results log, but found {len(results)}")

        for res in results:
            results = json.loads(res)
            self.assertEqual(results.get("hello"), "world",
                             msg="Expected results to have key 'hello' with value 'world', but they did not.")

    def test_flatten_results(self):
        """Make sure result flattening works as expected, as well as regular
        result output while we're at it."""

        arg_parser = arguments.get_parser()
        cmd = ['run', 'flatten_results']
        args = arg_parser.parse_args(cmd)

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.assertEqual(run_cmd.run(self.pav_cfg, args, log_results=False), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")

        series1 = run_cmd.last_series

        series1.log_results()

        try:
            series1.wait(10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series1.id} to complete after 10 seconds.")

        try:
            series1.wait_log(10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series1.id} to finish logging results after 10 seconds.")

        log_path = self.pav_cfg.working_dir / "results"
        matches = list(log_path.glob(f"{series1.id}*"))

        self.assertEqual(len(matches), 1,
                         msg=f"Expected exactly one log file matching '{series1.id}*', "
                             f"but found {len(matches)}: {matches}")

        result_log1 = next(iter(matches))

        flattened = {}

        with open(result_log1) as fin:
            lines = fin.readlines()

            for line in lines:
                _result = json.loads(line)

                # Reconstruct the per_file dict, so that flattened and
                # unflattened are the same. If there's a format error, this
                # will have problems.
                flattened[_result['file']] = {'hello': _result['hello']}

        answer = {
            '1': {'hello': 'hello 1'},
            '2': {'hello': 'hello 2'},
            '3': {'hello': 'hello 3'},
            '4': {'hello': 'hello 4'},
        }

        self.assertEqual(flattened, answer,
                        msg=f"Expected flattened results {answer} but found {flatten} instead.")

        self.pav_cfg["flatten_results"] = False

        self.assertEqual(run_cmd.run(self.pav_cfg, args, log_results=False), 0)

        series2 = run_cmd.last_series
        series1.outfile = io.StringIO()

        series2.log_results()

        series2.wait()
        series2.wait_log()

        matches = list(log_path.glob(f"{series2.id}*"))

        self.assertEqual(len(matches), 1,
                         msg=f"Expected exactly one log file matching '{series2.id}*', "
                             f"but found {len(matches)}: {matches}")

        result_log2 = next(iter(matches))

        unflattened = {}

        with open(result_log2) as fin:
            lines = fin.readlines()

            for line in lines:
                _result = json.loads(line)
                unflattened = _result["per_file"]

        self.assertEqual(unflattened, answer)

    def test_logging_process_exits_once_series_completed(self):
        """Test that the result logging process exits once the entire series has completed."""

        self.fail("This test is not yet implemented.")

    def test_logging_process_times_out_if_no_activity(self):
        """Test that the result logging process times out when tests are not active."""

        self.fail("This test is not yet implemented.")

    def test_load_custom_result_logger_plugin(self):
        """Test that custom result loggers can be loaded."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers=[{"plugin": "null_logger"}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        series = run_cmd.last_series

        series.wait_log(timeout=10)

    def test_logging_exits_if_no_loggers(self):
        """Test that the result logging process exits if there are no result loggers defined."""

        self.fail("This test is not yet implemented.")

    def test_logging_gracefully_handles_errors(self):
        """Test that the logging process gracefully handles ResultLoggerPluginErrors."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers=[{"plugin": "error_logger"}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        series = run_cmd.last_series

        series.wait_log(timeout=10)

    def test_series_file_result_logger_has_separate_files_for_reused_series_ids(self):
        """Test that when series IDs are used, the SeriesFileResultLogger gives them separate
        result logs."""

        self.fail("This test is not yet implemented.")

    def test_multiple_result_loggers(self):
        """Test that loggers work correctly when multiple loggers are defined."""