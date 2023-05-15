"""Command for showing fully resolved test config."""

import errno
import pprint

from pavilion import output
from pavilion import cmd_utils
from pavilion.commands import run
from pavilion.output import fprint
from pavilion import resolver
from .base_classes import Command
from ..errors import CommandError


class ViewCommand(run.RunCommand):
    """Command for showing fully resolved test config."""

    def __init__(self):  # pylint: disable=W0231

        # Use the base command class init
        # pylint: disable=non-parent-init-called
        Command.__init__(
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
            '-f', '--file', dest='files', action='append', default=[],
            help='Add tests listed in the given file, as per the "pav run" command',
        )
        parser.add_argument(
            'tests', action='store', nargs='*',
            help='The name of the test to view. Should be in the format'
                 '<suite_name>.<test_name>.')

    SLEEP_INTERVAL = 1

    def run(self, pav_cfg, args):
        """Resolve the test configurations into individual tests and assign to
        schedulers. Have those schedulers kick off jobs to run the individual
        tests themselves."""

        overrides = []
        for ovr in args.overrides:
            if '=' not in ovr:
                fprint(self.errfile, "Invalid override value. Must be in the form: "
                                     "<key>=<value>. Ex. -c run.modules=['gcc'] ")
                return errno.EINVAL

            key, value = ovr.split('=', 1)
            overrides[key] = value

        tests = args.tests

        self.logger.debug("Finding Configs")

        res = resolver.TestConfigResolver(pav_cfg)

        tests.extend(cmd_utils.read_test_files(pav_cfg, args.files))

        try:
            proto_tests = res.load(
                host=args.host,
                tests=tests,
                modes=args.modes,
                overrides=overrides,
                outfile=self.outfile,
            )
        except CommandError as err:
            fprint(self.errfile, err, color=output.RED)
            return errno.EINVAL

        configs = {pt.config['name']: pt.config for pt in proto_tests}
        pprint.pprint(configs, stream=self.outfile)  # ext-print: ignore
        return 0
