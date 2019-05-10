from collections import defaultdict
from pavilion import commands
from pavilion import schedulers
from pavilion import test_config
from pavilion.status_file import STATES
from pavilion.suite import Suite
from pavilion.test_config.string_parser import ResolveError
from pavilion.pavtest import PavTest
from pavilion import system_variables
import errno
import sys
import time


class RunCommand(commands.Command):

    def __init__(self):

        super().__init__('run', 'Setup and run a set of tests.',
                         short_help="Setup and run a set of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')
        parser.add_argument(
            '-c', dest='overrides', action='append', default=[],
            help='Overrides for specific configuration options. These are '
                 'gathered used as a final set of overrides before the '
                 'configs are resolved. They should take the form '
                 '\'key=value\', where key is the dot separated key name, '
                 'and value is a json object.')
        parser.add_argument(
            '-f', '--file', dest='files', action='append', default=[],
            help='One or more files to read to get the list of tests to run. '
                 'These files should contain a newline separated list of test '
                 'names. Lines that start with a \'#\' are ignored as '
                 'comments.')
        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            '-w', '--wait', action='store', type=int, default=None,
            help='Wait this many seconds to make sure at least one test '
                 'started before returning. If a test hasn\'t started by '
                 'then, cancel all tests and return a failure. Defaults to'
                 'not checking tests before returning.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name of the tests to run. These may be suite names (in '
                 'which case every test in the suite is run), or a '
                 '<suite_name>.<test_name>.')

    SLEEP_INTERVAL = 1

    def run(self, pav_cfg, args):
        """Resolve the test configurations into individual tests and assign to
        schedulers. Have those schedulers kick off jobs to run the individual
        tests themselves."""

        # 1. Resolve the test configs
        #   - Get sched vars from scheduler.
        #   - Compile variables.
        #

        overrides = {}
        for ovr in args.overrides:
            if '=' not in ovr:
                print("Invalid override value. Must be in the form: "
                      "<key>=<value>. Ex. -c run.modules=['gcc'] ")
                return errno.EINVAL

            key, value = ovr.split('=', 1)
            overrides[key] = value

        try:
            test_configs = self._get_tests(pav_cfg,
                                           args.host,
                                           args.files,
                                           args.tests,
                                           args.modes,
                                           overrides)
        except test_config.TestConfigError as err:
            print(err, file=sys.stderr)
            return errno.EINVAL

        all_tests = sum(test_configs.values(), [])

        if not all_tests:
            print("You must specify at least one test.", file=sys.stderr)
            return errno.EINVAL

        suite = Suite(pav_cfg, all_tests)

        # Building any tests that specify that they should be built before
        for test in all_tests:
            if test.config['build']['on_nodes'] not in ['true', 'True']:
                if not test.build():
                    print("Error building test: status {status.state} "
                          "- {status.note}"
                          .format(status=test.status))
                    return errno.EINVAL

        for sched_name, tests in test_configs.items():
            sched = schedulers.get_scheduler_plugin(sched_name)

            try:
                sched.schedule_tests(pav_cfg, tests)
            except schedulers.SchedulerPluginError as err:
                print(err)
                self._cancel_all(test_configs)

        # Tests should all be scheduled now, and have the SCHEDULED state
        # (at some point, at least). Wait until something isn't scheduled
        # anymore (either running or dead), or our timeout expires.
        wait_result = None
        if args.wait is not None:
            end_time = time.time() + args.wait
            while time.time() < end_time and wait_result is None:
                last_time = time.time()
                for sched_name, tests in test_configs.items():
                    sched = schedulers.get_scheduler_plugin(sched_name)
                    for test in tests:
                        status = test.status.current()
                        if status == STATES.SCHEDULED:
                            status = sched.job_status(pav_cfg, test)

                        if status != STATES.SCHEDULED:
                            # The test has moved past the scheduled state.
                            wait_result = None
                            break

                        break

                if wait_result is None:
                    # Sleep at most SLEEP INTERVAL seconds, minus the time
                    # we spent checking our jobs.
                    time.sleep(self.SLEEP_INTERVAL - (time.time() - last_time))

        print("{} tests started under as test series {}."
              .format(len(all_tests), suite.id))

        # TODO: Call pav status on the series.

        return 0

    def _get_tests(self, pav_cfg, host, test_files, tests, modes, overrides):
        """Translate a general set of pavilion test configs into the final,
        resolved configuration objects. These objects will be organized in a
        dictionary by scheduler, and have a scheduler object instantiated and
        attached.
        :param pav_cfg: The pavilion config
        :param str host: The host config to target these tests with
        :param list(str) modes: The mode configs to use.
        :param list(Path) test_files: Files containing a newline separated
            list of tests.
        :param list(str) tests: The tests to run.
        :param list(str) overrides: Overrides to apply to the configurations.
        :returns: A dictionary (by scheduler type name) of lists of test
            objects
        """
        self.logger.debug("Finding Configs")

        sys_vars = system_variables.get_vars(True)

        # Use the sys_host if a host isn't specified.
        if host is None:
            host = sys_vars.get('sys_host')

        tests = list(tests)
        for file in test_files:
            try:
                with file.open() as test_file:
                    for line in test_file.readlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            tests.append(line)
            except (OSError, IOError) as err:
                msg = "Could not read test file {}: {}".format(file, err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

        raw_tests = test_config.load_test_configs(pav_cfg, host, modes,
                                                  tests)
        raw_tests_by_sched = defaultdict(lambda: [])
        tests_by_scheduler = defaultdict(lambda: [])

        # Apply config overrides.
        for test_cfg in raw_tests:
            # Apply the overrides to each of the config values.
            try:
                test_config.apply_overrides(test_cfg, overrides)
            except test_config.TestConfigError as err:
                msg = 'Error applying overrides to test {} from {}: {}'\
                      .format(test_cfg['name'], test_cfg['suite_path'], err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

            # Resolve all configuration permutations.
            try:
                p_cfg, permutes = test_config.resolve_permutations(
                    test_cfg,
                    pav_cfg.pav_vars,
                    sys_vars
                )
                for p_var_man in permutes:
                    sched = p_cfg['scheduler'].resolve(p_var_man)
                    raw_tests_by_sched[sched].append((p_cfg, p_var_man))
            except test_config.TestConfigError as err:
                msg = 'Error resolving permutations for test {} from {}: {}'\
                      .format(test_cfg['name'], test_cfg['suite_path'], err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

        # Get the schedulers for the tests, and the scheduler variables. 
        # The scheduler variables are based on all of the
        for sched_name in raw_tests_by_sched.keys():
            try:
                sched = schedulers.get_scheduler_plugin(sched_name)
            except KeyError:
                msg = "Could not find scheduler '{}'.".format(sched_name)
                self.logger.error(msg)
                raise commands.CommandError(msg)

            nondeferred_cfg_sctns = schedulers.list_scheduler_plugins()

            # Builds must have the values of all their variables now.
            nondeferred_cfg_sctns.append('build')

            # Set the echeduler variables for each test.
            for test_cfg, test_var_man in raw_tests_by_sched[sched_name]:
                test_var_man.add_var_set('sched', sched.get_vars(test_cfg))

                # Resolve all variables for the test.
                try:
                    resolved_config = test_config.resolve_all_vars(
                        test_cfg,
                        test_var_man,
                        no_deferred_allowed=nondeferred_cfg_sctns)

                except (ResolveError, KeyError) as err:
                    msg = 'Error resolving variables in config: {}'.format(err)
                    self.logger.error(msg)
                    raise commands.CommandError(msg)

                test = PavTest(pav_cfg, resolved_config, sys_vars)

                tests_by_scheduler[sched.name].append(test)

        return tests_by_scheduler

    def _cancel_all(self, tests_by_sched):
        for sched_name, tests in tests_by_sched.items():

            sched = schedulers.get_scheduler_plugin(sched_name)

            for test in tests:
                sched.cancel_job(test)
