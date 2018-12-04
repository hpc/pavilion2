from pavilion import commands
from pavilion import sys


class RunCommand(commands.Command):

    def __init__(self):

        super().__init__('run', 'Setup and run a set of tests.', __file__)

    def _setup_arguments(self, parser):

        parser.add_argument('-H', '--host', action='store',
                            help='The host to configure this test for. If not specified, the '
                                 'current host as denoted by the sys plugin \'sys_host\' is used.')
        parser.add_argument('-m', '--mode', action='store', nargs='*',
                            help='Mode configurations to overlay on the host configuration for '
                                 'each test. These are overlayed in the order given.')
        parser.add_argument('-c', dest='config_overrides', action='store', nargs='*',
                            help='Overrides for specific configuration options. These are gathered'
                                 'used as a final set of overrides before the configs are'
                                 'resolved. They should take the form \'key=value\', '
                                 'where key is the dot separated key name, and value is a '
                                 'json object.')
        parser.add_argument('-f', '--file', action='store', nargs='*',
                            help='One or more files to read to get the list of tests to run. '
                                 'These files should contain a newline separated list of test '
                                 'names.')
        parser.add_argument('tests', nargs='*', action='store',
                            help='The name of the tests to run. These may be suite names (in '
                                 'which case every test in the suite is run), '
                                 'or a <suite_name>.<test_name>.')

    def run(self, pav_config, args):
        """Resolve the test configurations into individual tests and assign to schedulers.
        Have those schedulers kick off jobs to run the individual tests themselves."""

        self.logger.DEBUG("Finding Configs")

