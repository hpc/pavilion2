import errno
import pprint
import sys

from pavilion import commands
from pavilion import output
from pavilion import system_variables
from pavilion.plugins.commands import run
from pavilion.output import fprint


class ViewCommand(run.RunCommand):

    def __init__(self):  # pylint: disable=W0231

        # Use the base command class init
        # pylint: disable=non-parent-init-called
        commands.Command.__init__(
            self=self,
            name='view',
            description='Show the resolved config for a test.',
            short_help="Show the resolved config for a test."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlaid in the order given.')
        parser.add_argument(
            '-c', dest='overrides', action='append', default=[],
            help='Overrides for specific configuration options. These are '
                 'gathered used as a final set of overrides before the '
                 'configs are resolved. They should take the form '
                 '\'key=value\', where key is the dot separated key name, '
                 'and value is a json object.')
        parser.add_argument(
            'test', action='store',
            help='The name of the test to view. Should be in the format'
                 '<suite_name>.<test_name>.')

    SLEEP_INTERVAL = 1

    def run(self, pav_cfg, args):
        """Resolve the test configurations into individual tests and assign to
        schedulers. Have those schedulers kick off jobs to run the individual
        tests themselves.
        :param err_file: """

        overrides = {}
        for ovr in args.overrides:
            if '=' not in ovr:
                fprint("Invalid override value. Must be in the form: "
                       "<key>=<value>. Ex. -c run.modules=['gcc'] ",
                       file=self.errfile)
                return errno.EINVAL

            key, value = ovr.split('=', 1)
            overrides[key] = value

        tests = [args.test]

        self.logger.debug("Finding Configs")

        sys_vars = system_variables.get_vars(True)

        try:
            configs_by_sched = self.get_test_configs(pav_cfg=pav_cfg,
                                                     host=args.host,
                                                     test_files=[],
                                                     tests=tests,
                                                     modes=args.modes,
                                                     overrides=overrides)
        except commands.CommandError as err:
            fprint(err, file=self.errfile, color=output.RED)
            return errno.EINVAL

        configs = []
        for conf_tuples in configs_by_sched.values():
            configs.extend([conf for conf, _ in conf_tuples])

        for config in configs:
            pprint.pprint(config, stream=self.outfile)  # ext-print: ignore
