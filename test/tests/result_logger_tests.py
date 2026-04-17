import json
import io
import os
import signal
import shutil

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase
from pavilion.result_logging import get_result_loggers
from pavilion.counter import SeriesIDCounter


class ResultLoggerTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.link_files(
                    "suites/hello_world.yaml",
                    "suites/results_log.yaml",
                    "suites/flatten_results.yaml",
                    "suites/forever.yaml",
                    "plugins/schedulers/dummy.*",
                    "plugins/result_logger/error_logger.*",
                    "plugins/result_logger/null_logger.*")

        # We'll use this to keep track of logging processes so we can kill them during tear_down
        self.series = []

    def set_up(self):
        os.environ["PAV_CONFIG_DIR"] = self.pav_config_dir.as_posix()
        plugins.initialize_plugins(self.pav_cfg)
        self.series = []

    def tear_down(self):
        """Kill any lingering logging processes."""

        for series in self.series:
            if series.log_proc is not None:
                try:
                    os.kill(series.log_proc.pid, signal.SIGTERM)
                    series.log_proc.wait(2)
                except ProcessLookupError:
                    continue

    def test_series_file_logger(self):
        """Test that the series file logger works correctly."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers= [{
                                                "plugin": "series_file",
                                                "dest": self.results_dir.as_posix()}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")

        series = run_cmd.last_series
        self.series.append(series)

        try:
            series.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series.id} to finish logging results after 10 seconds.")

        matches = list(self.results_dir.glob(f"{series.id}*"))

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

        log_path = self.results_dir / "results.log"
        self.pav_cfg = self.make_pav_config(result_loggers=[{
                                                "plugin": "common_file",
                                                "dest": log_path.as_posix()}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")
        series1 = run_cmd.last_series
        self.series.append(series1)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")
        series2 = run_cmd.last_series
        self.series.append(series2)

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
        """Make sure result flattening works as expected."""

        arg_parser = arguments.get_parser()
        cmd = ['run', 'flatten_results']
        args = arg_parser.parse_args(cmd)

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers=[{
                                        "plugin": "series_file",
                                        "dest": self.results_dir}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args, log_results=False), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")

        series1 = run_cmd.last_series
        self.series.append(series1)

        series1.log_results()

        try:
            series1.wait(10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series1.id} to complete after 10 seconds.")

        try:
            series1.wait_log(10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series1.id} to finish logging results after 10 seconds.")

        log_path = self.results_dir
        matches = list(log_path.glob(f"{series1.id}*"))

        self.assertEqual(len(matches), 1,
                         msg=f"Expected exactly one log file matching '{series1.id}*', "
                             f"but found {len(matches)}: {matches}")

        result_log1 = next(iter(matches))

        actual = {}

        with open(result_log1) as fin:
            lines = fin.readlines()

            for line in lines:
                _result = json.loads(line)

                # Reconstruct the per_file dict, so that flattened and
                # unflattened are the same. If there's a format error, this
                # will have problems.
                actual[_result['file']] = {'hello': _result['hello']}

        expected = {
            '1': {'hello': 'hello 1'},
            '2': {'hello': 'hello 2'},
            '3': {'hello': 'hello 3'},
            '4': {'hello': 'hello 4'},
        }

        self.assertEqual(actual, expected,
                        msg=f"Expected flattened results {expected} for {series1.id} but found {actual} instead.")

        self.pav_cfg = self.make_pav_config(
                                    result_loggers=[{
                                        "plugin": "series_file",
                                        "dest": self.results_dir}],
                                    flatten_results=False)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        series2 = run_cmd.last_series
        self.series.append(series2)

        try:
            series2.wait(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series2.id} to complete after 10 seconds.")

        try:
            series2.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series2.id} to finish loggging after 10 seconds.")

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

        self.assertEqual(unflattened, expected)

    def test_logging_process_exits_once_series_completed(self):
        """Test that the result logging process exits once the entire series has completed."""

        self.pav_cfg = self.make_pav_config(result_loggers= [
                                                {"plugin": "series_file",
                                                 "dest": self.results_dir.as_posix()},
                                                {"plugin": "common_file",
                                                 "dest": (self.results_dir / "results.log").as_posix()
                                                }])

        arg_parser = arguments.get_parser()
        cmd = ['run', 'hello_world*3']
        args = arg_parser.parse_args(cmd)

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0, msg=f"pav run hello_world*3 failed with the following output:\n{run_cmd.errfile.getvalue()}")

        last_series = run_cmd.last_series
        self.series.append(last_series)

        try:
            last_series.wait(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {last_series.id} to complete after 10 seconds.")

        self.assertNotEqual(last_series.log_proc, None,
                            msg=f"Series {last_series.id} does not appear to have started a logging process.")

        try:
            last_series.wait_log(timeout=2)
        except TimeoutError:
            self.fail(f"Result logging process for series {last_series.id} did not terminate, even though the series completed.")

        self.assertTrue((self.results_dir / "results.log").exists(),
                        msg=f"Common file logger did not create a results log at {self.results_dir / 'results.log'}")

        matches = list(self.results_dir.glob(f"{last_series.id}*"))

        self.assertEqual(len(matches), 1,
                         msg=f"Expected exactly one log file matching '{last_series.id}*', "
                             f"but found {len(matches)}: {matches}")

    def test_logging_process_times_out_if_no_activity(self):
        """Test that the result logging process times out when tests are not active."""

        self.pav_cfg = self.make_pav_config(result_loggers= [
                                                {"plugin": "common_file",
                                                    "dest": (self.results_dir / "results.log").as_posix()
                                                }],
                                            result_logger_timeout=3)
        arg_parser = arguments.get_parser()
        cmd = ['run', 'forever']
        args = arg_parser.parse_args(cmd)

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0, f"pav run forever failed with the following output:\n{run_cmd.errfile.getvalue()}")

        last_series = run_cmd.last_series
        self.series.append(last_series)

        self.assertNotEqual(last_series.log_proc, None,
                    msg=f"Series {last_series.id} does not appear to have started a logging process.")

        try:
            last_series.wait_log(timeout=5)
        except TimeoutError:
            last_series.cancel()
            self.fail(f"Result logging process for series {last_series.id} should have timed out, but didn't.")

        last_series.cancel()
        output = ""

        with open(last_series.path / last_series.LOG_RESULTS_LOG_FN) as fin:
            output = fin.read()

        self.assertTrue("has not been active" in output, msg=f"Series {last_series.id} did not log a timeout message to the result logger log.")

    def test_load_custom_result_logger_plugin(self):
        """Test that custom result loggers can be loaded."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers=[{"plugin": "null_logger"}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")
        series = run_cmd.last_series
        self.series.append(series)

        try:
            series.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series.id} to finish logging results after 10 seconds.")

        with open(series.path / series.LOG_RESULTS_LOG_FN) as fin:
            output = fin.read()

        self.assertFalse("Traceback" in output, msg=f"There was an error loading the result logger:\n{output}")
        self.assertFalse("Error making result loggers" in output, msg=f"Result logging encountered an error:\n{output}")
        self.assertTrue("NullResultLogger" in output, msg=f"Result logger for series {series.id} does not appear to have run.")

    def test_logging_exits_if_no_loggers(self):
        """Test that the result logging process exits if there are no result loggers defined."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers=[])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run results_log failed with the following output:\n{run_cmd.errfile.getvalue()}")
        series = run_cmd.last_series
        self.series.append(series)

        try:
            series.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series.id} to finish logging results after 10 seconds.")

        with open(series.path / series.LOG_RESULTS_LOG_FN) as fin:
            output = fin.read()

        self.assertFalse("Traceback" in output, msg=f"Result logging encountered an error:\n{output}")
        self.assertFalse("Error making result loggers" in output, msg=f"Result logging encountered an error:\n{output}")
        self.assertTrue("No loggers registered" in output)

    def test_logging_gracefully_handles_errors(self):
        """Test that the logging process gracefully handles ResultLoggerPluginErrors."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args(['run', 'results_log'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        self.pav_cfg = self.make_pav_config(result_loggers=[{"plugin": "error_logger"}])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        series = run_cmd.last_series
        self.series.append(series)

        try:
            series.wait(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series.id} to complete after 10 seconds.")

        try:
            series.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {series.id} to finish logging results after 10 seconds.")

        with open(series.path / series.LOG_RESULTS_LOG_FN) as fin:
            output = fin.read()

        self.assertFalse("Traceback" in output, msg=f"Result logging encountered an error:\n{output}")
        self.assertFalse("Error making result loggers" in output, msg=f"Result logging encountered an error:\n{output}")
        self.assertTrue("This error was raised deliberately" in output)

    def test_series_file_result_logger_has_separate_files_for_reused_series_ids(self):
        """Test that when series IDs are reused, the SeriesFileResultLogger gives them separate
        result logs."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args(['run', 'hello_world'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()

        reused_series_wd = self.suite_output_dir / "reused_series_wd"
        reused_series_wd.mkdir()

        reused_series_results_dir = self.suite_output_dir / "results_series_results"
        reused_series_results_dir.mkdir()

        self.pav_cfg = self.make_pav_config(result_loggers=[{
                                "plugin": "series_file",
                                "dest": reused_series_results_dir.as_posix()}], working_dir=reused_series_wd.as_posix())

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                         msg=f"pav run hello_world failed with the following output:\n{run_cmd.errfile.getvalue()}")

        last_series = run_cmd.last_series
        self.series.append(last_series)

        try:
            last_series.wait(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {last_series.id} to complete after 10 seconds.")

        try:
            last_series.wait_log(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {last_series.id} to finish logging results after 10 seconds.")

        # Reset the test ID
        SeriesIDCounter(reused_series_wd / "series").reset()

        shutil.rmtree(last_series.path)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0,
                    msg=f"pav run hello_world failed with the following output:\n{run_cmd.errfile.getvalue()}")

        last_series = run_cmd.last_series
        self.series.append(last_series)

        try:
            last_series.wait(timeout=10)
        except TimeoutError:
            self.fail(f"Timed out waiting for series {last_series.id} to complete after 10 seconds.")

        matches = list(reused_series_results_dir.glob(f"{last_series.id}*"))

        self.assertEqual(len(matches), 2,
                         msg=f"Expected exactly 2 log files matching '{last_series.id}*', "
                             f"but found {len(matches)}: {matches}")