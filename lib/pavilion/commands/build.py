"""The build commands builds tests, but does not run them. It is actually
the run command with a few different options."""

from pavilion import commands
from pavilion.plugins.commands import run as run_plugin


class BuildCommand(run_plugin.RunCommand):
    """Build tests locally, and kick off any that require building on nodes."""

    BUILD_ONLY = True

    def __init__(self):

        # pylint: disable=non-parent-init-called
        # pylint: disable=super-init-not-called
        commands.Command.__init__(
            self,
            name="build",
            description="Perform just the build step on the given tests, "
                        "or perform rebuilds. May still use the scheduler"
                        "to build tests that specify they must be built on "
                        "nodes.",
            short_help="Build and re-build.",
        )

    def _setup_arguments(self, parser):
        """Most of our arguments come from the run command."""

        self._generic_arguments(parser)

        parser.add_argument(
            '-l', '--local-builds-only', action='store_true', default=False,
            help="Only build locally, don't kickoff builds on nodes.")
        parser.add_argument(
            '-f', '--file', dest='files', action='append', default=[],
            help='One or more files to read to get the list of tests to build. '
                 'These files should contain a newline separated list of test '
                 'names. Lines that start with a \'#\' are ignored as '
                 'comments.')
