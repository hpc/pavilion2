"""Command for showing fully resolved test config."""

import errno
import pprint
from pavilion.test_config import file_format

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
        """Define command‑line arguments for the view command.

        The existing arguments are retained and the new ``--stack`` flag is added.
        """
        parser.add_argument(
            '-p', '--platform', action='store',
            help='The platform to configure this test for. If not specified, the '
                 "current operating system as denoted by the sys plugin 'sys_os' is used.")
        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 "current host as denoted by the sys plugin 'sys_host' is used.")
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for each test. '
                 "These are overlaid in the order given.")
        parser.add_argument(
            '-c', dest='overrides', action='append', default=[],
            help='Overrides for specific configuration options. These are '
                 "gathered used as a final set of overrides before the configs are resolved. "
                 "They should take the form 'key=value', where key is the dot separated key name, "
                 "and value is a json object.")
        parser.add_argument(
            '--stack', action='store_true', default=False,
            help='Show the unmerged configuration stack for each test, including base config, '
                 "suite inheritance, and platform/host/mode configs.")
        parser.add_argument(
            '-f', '--file', dest='files', action='append', default=[],
            help='Add tests listed in the given file, as per the "pav run" command')
        parser.add_argument(
            'tests', action='store', nargs='*',
            help='The name of the test to view. Should be in the format <suite_name>.<test_name>.')

    SLEEP_INTERVAL = 1

    # pylint: disable=arguments-differ
    def run(self, pav_cfg, args, log_results: bool = True):
        """Resolve the test configurations into individual tests and assign to
        schedulers. Have those schedulers kick off jobs themselves.

        ``log_results`` is retained for compatibility with ``RunCommand``.
        """

        # ``args.overrides`` is already a list of ``key=value`` strings.
        # The resolver expects this list directly, so we pass it through.
        overrides = args.overrides

        # ---------------------------------------------------------------------
        # ``--stack`` handling – show the unmerged configuration stack.
        # ---------------------------------------------------------------------
        if getattr(args, 'stack', False):
            # Use the new resolver method to get the unmerged config stack.
            resolver_obj = resolver.TestConfigResolver(pav_cfg)

            for full_name in args.tests:
                try:
                    stack = resolver_obj.get_unmerged_config_stack(
                        full_test_name=full_name,
                        modes=args.modes,
                        platform=args.platform,
                        host=args.host,
                        overrides=args.overrides,
                    )
                except Exception as err:
                    fprint(self.errfile, f"Could not get stack for {full_name}: {err}", color=output.RED)
                    continue

                fprint(self.outfile, f"Config stack for {full_name}:")
                for label, cfg, path in stack:
                    if path:
                        fprint(self.outfile, f"# path: {path}")
                    else:
                        fprint(self.outfile, "# generated in‑memory")
                    fprint(self.outfile, f"--- {label} ---")
                    pprint.pprint(cfg, stream=self.outfile)

            return 0

        # ---------------------------------------------------------------------
        # Normal ``pav view`` – show fully resolved configuration.
        # ---------------------------------------------------------------------
        tests = args.tests

        self.logger.debug("Finding Configs")

        res = resolver.TestConfigResolver(pav_cfg, platform=args.platform,
                                          host=args.host, outfile=self.outfile)

        tests.extend(cmd_utils.read_test_files(pav_cfg, args.files))

        try:
            proto_tests = res.load(
                tests=tests,
                modes=args.modes,
                overrides=overrides,
            )
        except CommandError as err:
            fprint(self.errfile, err, color=output.RED)
            return errno.EINVAL

        configs = {pt.config['name']: pt.config for pt in proto_tests}
        pprint.pprint(configs, stream=self.outfile)  # ext-print: ignore
        return 0

        tests = args.tests

        self.logger.debug("Finding Configs")

        res = resolver.TestConfigResolver(pav_cfg, platform=args.platform,
                                          host=args.host, outfile=self.outfile)

        tests.extend(cmd_utils.read_test_files(pav_cfg, args.files))

        try:
            proto_tests = res.load(
                tests=tests,
                modes=args.modes,
                overrides=overrides,
            )
        except CommandError as err:
            fprint(self.errfile, err, color=output.RED)
            return errno.EINVAL

        configs = {pt.config['name']: pt.config for pt in proto_tests}
        pprint.pprint(configs, stream=self.outfile)  # ext-print: ignore
        return 0
