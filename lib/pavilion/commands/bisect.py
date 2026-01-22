from argparse import ArgumentParser, Namespace
from typing import List

from pavilion import output
from pavilion.errors import TestSeriesError
from pavilion.config import PavConfig
from pavilion.series.series import TestSeries
from pavilion.schedulers.config import parse_node_range
from .base_classes import Command


class BisectCommand(Command):
    """Identify bad nodes by using a test to perform a binary search."""

    def __init__(self):
        super().__init__(
            'bisect',
            'Perform a bisection search on a given set of nodes using a particular test.',
            short_help="Perform a bisection search."
        )

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        """Set up the parser arguments."""

        parser.add_argument("test_name", type=str,
                help="The name of the test to use to bisect the nodes.")
        parser.add_argument("nodes", type=str, default="",
                help="The set of nodes with which to start the search.")
        parser.add_argument(
            '-p', '--platform', action='store',
            help='The platform to configure this test for. If not '
            'specified, the current platform as denoted by the sys '
            'plugin \'platform\' is used.')
        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used. Host configurations are overlayed on operating system '
                 'configurations.')
        parser.add_argument(
            '-n', '--name', action='store', default=''
        )
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
                 'and value is a json object. Example: `-c schedule.nodes=23`')

    def run(pav_cfg: PavConfig, args: Namespace) -> int:
        """Run the bisection search."""

        try:
            nodes = self._parse_nodes(args.nodes)
        except ValueError:
            output.fprint(self.errfile, f"Error parsing node list {args.nodes}.")

            return 1

        # 1. Split the set of nodes in half.
        num_nodes = len(nodes)
        first_half = nodes[:num_nodes]
        second_half = nodes[num_nodes:]

        # 2. Run the test on each set of nodes
        series_cfg = generate_series_config(
            name="bisect",
            modes=args.modes,
            platform=args.platform,
            host=args.host,
            overrides=args.overrides,
            ignore_errors=args.ignore_errors,
        )

        series_obj = TestSeries(pav_cfg, series_cfg=series_cfg, outfile=self.outfile)
        testset_name = cmd_utils.get_testset_name(pav_cfg, [args.test_name], [])

        series_obj.add_test_set_config(
            testset_name,
            [args.test_name],
            modes=args.modes,
        )

        self.last_series = series_obj

        try:
            series_obj.run(
                rebuild=args.rebuild,
                local_builds_only=local_builds_only,
                log_results=log_results)
            self.last_tests = list(series_obj.tests.values())
        except TestSeriesError as err:
            self.last_tests = list(series_obj.tests.values())
            output.fprint(self.errfile, err, color=output.RED)

            return 2

        # 3. Wait for tests to finish
        series_obj.wait()

        # 4. Choose test with failed nodes and repeat

        return 0

    @staticmethod
    def _parse_nodes(nodes: str) -> List[str]:
        """Parse a list of nodes into individual nodes."""

        nodes = []

        ranges = nodes.split(",")

        for rng in ranges:
            nodes.append(parse_node_range(rng))

        return nodes