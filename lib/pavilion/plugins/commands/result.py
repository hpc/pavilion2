from pavilion import commands
from pavilion import series
from pavilion.pav_test import PavTest, PavTestError, PavTestNotFoundError
from pavilion import utils
import sys


class ResultsCommand(commands.Command):

    def __init__(self):

        super().__init__(
            name="results",
            aliases=['result'],
            description="Displays results from the given tests.",
            short_help="Displays results from the given tests."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            "-j", "--json",
            action="store_true", default=False,
            help="Give the results in json."
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-k", "--key",
            action='append', nargs="*", default=[],
            help="Additional result keys to display."
        )
        group.add_argument(
            "-f", "--full", action="store_true", default=False,
            help="Show all result keys."
        )
        parser.add_argument(
            "tests",
            nargs="*",
            help="The tests to show the results for."
        )

    def run(self, pav_config, args):

        test_ids = self._get_tests(pav_config, args.tests)

        tests = []
        for id_ in test_ids:
            try:
                tests.append(PavTest.load(pav_config, id_))
            except PavTestError as err:
                self.logger.warning("Could not load test '{}': {}"
                                    .format(id_, err))
            except PavTestNotFoundError as err:
                self.logger.warning("Could not find test '{}': {}"
                                    .format(id_, err))

        results = []
        for test in tests:
            res = test.load_results()
            if res is None:
                res = {
                    'name': test.name,
                    'id': test.id,
                    'result': ''
                }

            results.append(res)

        all_keys = set()
        for res in results:
            all_keys = all_keys.union(res.keys())

        all_keys = list(all_keys.difference(['result', 'name', 'id']))
        # Sort the keys by the size of the data
        all_keys.sort(key=lambda k: max([len(res[k]) for res in results]))

        print(all_keys)

        if args.json:
            utils.json_dump(results, sys.stdout)
            return 0

        if args.full:
            fields = ['name', 'id', 'result'] + all_keys
        else:
            fields = ['name', 'id', 'result'] + args.key

        utils.draw_table(
            outfile=sys.stdout,
            field_info={},
            fields=fields,
            rows=results,
            title="Test Results"
        )

    def _get_tests(self, pav_cfg, tests_arg):
        if not tests_arg:
            # Get the last series ran by this user.
            series_id = series.TestSeries.load_user_series_id()
            if series_id is not None:
                tests_arg.append('s{}'.format(series_id))

        test_list = []
        for test_id in tests_arg:
            if test_id.startswith('s'):
                try:
                    test_list.extend(
                        series.TestSeries.from_id(
                            pav_cfg,
                            int(test_id[1:])).tests)
                except series.TestSeriesError as err:
                    self.logger.warning(
                        "Suite {} could not be found.\n{}"
                            .format(test_id[1:], err),
                    )
                    continue
            else:
                test_list.append(test_id)

        return map(int, test_list)
