import os

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase
from pavilion.test_run import TestRun
from pavilion.test_ids import TestID
from pavilion.resolver import TestConfigResolver, TestRequest


class MultiConfigTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        # Don't automatically create the pav_config_dir or working_dir
        super().__init__(*args, **kwargs)

        arg_parser = arguments.get_parser()
        config_cmd = commands.get_command('config')
        config_cmd.silence()

        # Create secondary config directory and working directory
        self.config_dir2 = self.suite_output_dir / "pav_config_dir2"
        self.working_dir2 = self.suite_output_dir / "working_dir2"

        self.working_dir2.mkdir(exist_ok=True)

        args = arg_parser.parse_args(["config", "create", "config_dir2", self.config_dir2.as_posix(),
                                      "--working_dir", self.working_dir2.as_posix()])

        config_cmd.run(self.pav_cfg, args)

        # Link into main config directory
        self.link_files(
            "suites/hello_world.yaml",
            "plugins/schedulers/dummy.*")

        # Link into second config_directory
        self.link_files(
            "suites/echo_test.yaml",
            "modes/smode2.yaml",
             config_dir=self.config_dir2)

    def set_up(self):
        try:
            (self.config_dir2 / "suites" / "hello_world.yaml").unlink()
            (self.config_dir2 / "test_src" / "hello.c").unlink()
        except FileNotFoundError:
            pass

        # Reload the pav config so that it has the new config directory and correct suite info
        self.pav_cfg = self.make_pav_config(config_dirs=[self.config_dir2])

        self.assertEqual(len(self.pav_cfg.configs), 3,
                         msg="Expected exactly 3 configs in the Pavilion config, but found "
                             f"{len(self.pav_cfg.configs)}:\n{[(label, cfg.path) for label, cfg in self.pav_cfg.configs.items()]}")
        self.assertEqual(len(self.pav_cfg.config_dirs), 1,
                         msg="Expected exactly 1 config directory in the Pavilion config, but found "
                             f"{len(self.pav_cfg.configs)}: {self.pav_cfg.config_dirs}")

        os.environ["PAV_CONFIG_DIR"] = self.pav_config_dir.as_posix()
        plugins.initialize_plugins(self.pav_cfg)

        run_cmd = commands.get_command("run")
        run_cmd.silence()

        arg_parser = arguments.get_parser()
        run_args = arg_parser.parse_args(["run", "hello_world"])

        self.assertEqual(run_cmd.run(self.pav_cfg, run_args), 0,
                         msg=f"pav run hello_world failed with the following output:\n{run_cmd.errfile.getvalue()}")

        self.series1 = run_cmd.last_series

        run_args = arg_parser.parse_args(["run", "-m", "smode2", "echo_test"])

        self.assertEqual(run_cmd.run(self.pav_cfg, run_args), 0,
                         msg=f"pav run echo_test failed with the following output:\n{run_cmd.errfile.getvalue()}")

        self.series2 = run_cmd.last_series

        try:
            self.series1.wait(timeout=self.series_wait_timeout)
        except TimeoutError:
            self.fail(msg=f"Timed out waiting for series {self.series1.id} to complete after {self.series_wait_timeout} seconds.")

        try:
            self.series2.wait(timeout=self.series_wait_timeout)
        except TimeoutError:
            self.fail(msg=f"Timed out waiting for series {self.series2.id} to complete after {self.series_wait_timeout} seconds.")

    def test_test_runs_in_correct_working_dir(self):
        """Test that each test run is placed in the working directory that corresponds to the
        config directory from which the test originated."""

        self.assertEqual(len(self.pav_cfg.suite_info), 2,
                    msg="Expected exactly 2 suite info tuples on the Pavilion config, "
                        f"but found {len(self.pav_cfg.suite_info)}: {self.pav_cfg.suite_info}")

        self.assertTrue((self.working_dir / "test_runs" / f"{self.series1.id}.1").exists(),
                         msg=f"Series {self.series1.id} did not create its test run directories in {self.working_dir}")
        self.assertTrue((self.working_dir2 / "test_runs" / f"{self.series2.id}.1").exists(),
                         msg=f"Series {self.series2.id} did not create its test run directories in {self.working_dir2}")

    def test_series_dirs_created_in_main_working_dir(self):
        """Test that series directories are created in the main working directory, regardless of
        where their tests suites originated from."""

        self.assertEqual(len(self.pav_cfg.suite_info), 2,
            msg="Expected exactly 2 suite info tuples on the Pavilion config, "
                f"but found {len(self.pav_cfg.suite_info)}: {self.pav_cfg.suite_info}")

        self.assertTrue((self.working_dir / "series" / str(self.series1.id.as_int())).exists(),
                        msg=f"Expected directory for {self.series1.id} to exist at {self.working_dir / 'series' / str(self.series1.id.as_int())}, but it does not.")
        self.assertTrue((self.working_dir / "series" / str(self.series2.id.as_int())).exists(),
                        msg=f"Expected directory for {self.series2.id} to exist at {self.working_dir / 'series' / str(self.series2.id.as_int())}, but it does not.")

    def test_test_runs_loaded_from_correct_working_dir(self):
        """Test that test runs are loaded from the correct directory."""

        self.assertEqual(len(self.pav_cfg.suite_info), 2,
            msg="Expected exactly 2 suite info tuples on the Pavilion config, "
                f"but found {len(self.pav_cfg.suite_info)}: {self.pav_cfg.suite_info}")

        test1_id = TestID(f"{self.series1.id}.1")
        test1 = TestRun.load(self.pav_cfg, test1_id)
        self.assertEqual(test1.path, self.working_dir / "test_runs" / str(test1_id),
                         msg=f"Test {test1_id} has the wrong path. Expected {self.working_dir / 'test_runs' / str(test1_id)} "
                             f"but found {test1.path}")

        test2_id = TestID(f"{self.series2.id}.1")
        test2 = TestRun.load(self.pav_cfg, test2_id)
        self.assertEqual(test2.path, self.working_dir2 / "test_runs" / str(test2_id),
                         msg=f"Test {test2_id} has the wrong path. Expected {self.working_dir2 / 'test_runs' / str(test2_id)} "
                             f"but found {test2.path}")

    def test_same_name_suite_in_different_config_dirs(self):
        """Test that Pavilion prefers suites from the main configuration directory when multiple
        suites exist with the same name."""

        self.link_file("suites/hello_c.yaml", config_dir=self.config_dir2, with_name="hello_world.yaml")
        self.link_file("test_src/hello.c", config_dir=self.config_dir2)

        # Reload the pav config so that it has the new config directory and correct suite info
        self.pav_cfg = self.make_pav_config(config_dirs=[self.config_dir2])

        self.assertEqual(len(self.pav_cfg.suite_info), 3,
                         msg="Expected exactly 3 suite info tuples on the Pavilion config, "
                             f"but found {len(self.pav_cfg.suite_info)}: {self.pav_cfg.suite_info}")

        resolver = TestConfigResolver(self.pav_cfg)
        suites = resolver._load_suite_tests(TestRequest("hello_world"))

        self.assertEqual(len(suites), 2,
                         msg="Expected exactly 2 suites to be found for test request 'hello_world', "
                             f"but {len(suites)} were found.")

        self.assertTrue("hello" in suites.get(("_main", "hello_world")),
                        msg="Expected hello_world suite from main config directory.")

        self.assertTrue("hello_c" in suites.get(("config_dir2", "hello_world")),
                msg="Expected hello_world suite from secondary config directory.")