from collections import defaultdict
from pavilion import commands
from pavilion import config
from pavilion import pav_test
from pavilion import scheduler_plugins
from pavilion.string_parser import ResolveError


class RunCommand(commands.Command):

    def __init__(self):

        super().__init__('run', 'Setup and run a set of tests.', __file__)

    def _setup_arguments(self, parser):

        parser.add_argument('-H', '--host', action='store',
                            help='The host to configure this test for. If not specified, the '
                                 'current host as denoted by the sys plugin \'sys_host\' is used.')
        parser.add_argument('-m', '--mode', action='store', dest='modes', nargs='*',
                            help='Mode configurations to overlay on the host configuration for '
                                 'each test. These are overlayed in the order given.')
        parser.add_argument('-c', dest='config_overrides', action='store', nargs='*',
                            help='Overrides for specific configuration options. These are gathered'
                                 'used as a final set of overrides before the configs are'
                                 'resolved. They should take the form \'key=value\', '
                                 'where key is the dot separated key name, and value is a '
                                 'json object.')
        parser.add_argument('-f', '--file', action='store', dest='files', nargs='*',
                            help='One or more files to read to get the list of tests to run. '
                                 'These files should contain a newline separated list of test '
                                 'names. Lines that start with a \'#\' are ignored as comments.')
        parser.add_argument('tests', nargs='*', action='store',
                            help='The name of the tests to run. These may be suite names (in '
                                 'which case every test in the suite is run), '
                                 'or a <suite_name>.<test_name>.')

    def run(self, pav_config, args):
        """Resolve the test configurations into individual tests and assign to schedulers.
        Have those schedulers kick off jobs to run the individual tests themselves."""

        # 1. Resolve the test configs
        #   - Get sched vars from scheduler.
        #   - Compile variables.
        #

        test_configs = self.get_tests(pav_config, args)

        for sched_name, tests in test_configs.items():
            sched = scheduler_plugins.get_scheduler_plugin(sched_name)

            sched.run_tests(tests)

    def get_tests(self, pav_config, args):
        """Translate a general set of pavilion test configs into the final, resolved
        configuration objects. These objects will be organized in a dictionary by scheduler,
        and have a scheduler object instantiated and attached.
        :returns: A dictionary (by scheduler type name) of lists of test objects
        """
        self.logger.DEBUG("Finding Configs")

        # Use the sys_host if a host isn't specified.
        if args.host is None:
            host = pav_config.sys_vars.get('sys_host')
        else:
            host = args.host

        tests = args.tests
        for file in args.files:
            try:
                with open(file) as test_file:
                    for line in test_file.readlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            tests.append(line)
            except (OSError, IOError) as err:
                msg = "Could not read test file {}: {}".format(file, err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

        raw_tests = config.get_tests(pav_config, host, args.mode, tests)
        raw_tests_by_scheduler = defaultdict(lambda: [])
        tests_by_scheduler = defaultdict(lambda: [])

        # Apply config overrides.
        for test_cfg in raw_tests:
            # Apply the overrides to each of the config values.
            try:
                config.apply_overrides(test_cfg, args.overrides)
            except config.TestConfigError as err:
                msg = 'Error applying overrides to test {} from {}: {}'\
                      .format(test_cfg['name'], test_cfg['suite_path'], err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

            # Resolve all configuration permutations.
            try:
                for p_cfg, p_var_man in config.resolve_permutations(test_cfg,
                                                                    pav_config.pav_vars,
                                                                    pav_config.sys_vars):

                    raw_tests_by_scheduler[p_cfg['scheduler']].append((p_cfg, p_var_man))
            except config.TestConfigError as err:
                msg = 'Error resolving permutations for test {} from {}: {}'\
                      .format(test_cfg['name'], test_cfg['suite_path'], err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

        # Get the schedulers for the tests, and the scheduler variables. The scheduler variables
        # are based on all of the
        for sched_name in raw_tests_by_scheduler.keys():
            try:
                sched = scheduler_plugins.get_scheduler_plugin(sched_name)
            except KeyError:
                msg = "Could not find scheduler '{}'.".format(sched_name)
                self.logger.error(msg)
                raise commands.CommandError(msg)

            # Get the dictionary of scheduler variables (mostly deferred).
            sched_vars = sched.get_vars()

            sched_config_sections = scheduler_plugins.list_scheduler_plugins()

            # Set the echeduler variables for each test.
            for test_cfg, test_var_man in raw_tests_by_scheduler[sched_name]:
                test_var_man.add_var_set('sched', sched.vars)

                # Resolve all variables for the test.
                try:
                    resolved_config = config.resolve_all_vars(
                        test_cfg,
                        test_var_man,
                        no_deferred_allowed=sched_config_sections)

                except (ResolveError, KeyError) as err:
                    msg = 'Error resolving variables in config: {}'.format(err)
                    self.logger.error(msg)
                    raise commands.CommandError(msg)

                test = pav_test.PavTest(pav_config, resolved_config)

                tests_by_scheduler[sched.name].append(test)

        return tests_by_scheduler
















