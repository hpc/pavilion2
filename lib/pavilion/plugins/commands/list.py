"""A command to (relatively) quickly list tests, series, and other (as yet
undefined) bits."""

import datetime
import errno
import pwd

from pavilion import commands
from pavilion import dir_db
from pavilion import filters
from pavilion import output
from pavilion.commands import sub_cmd
from pavilion.series import TestSeries, TestSeriesError
from pavilion.test_run import TestAttributes


class ListCommand(commands.Command):
    """List test runs, series, and other bits."""

    def __init__(self):

        super().__init__(
            name='list',
            short_help="Quickly and compactly list Pavilion test runs or "
                       "series.",
            description="List test runs or series with minimal information. For"
                        "more detailed info, use 'pav status'. This command "
                        "is for getting a filtered list of tests or series "
                        "that can easily be fed directly to other commands. "
                        "By default the output is a space separated list of "
                        "items."
        )

    def _setup_arguments(self, parser):

        self._parser = parser

        parser.add_argument(
            '-1', action='store_const', default=False, dest='line_sep',
            const='\n',
            help="List the results one per line.")
        output_fields = parser.add_mutually_exclusive_group()
        output_fields.add_argument(
            '--long', '-l', action='store_true', default=False,
            help="Give additional info, depending on what is being listed. "
                 "Implies -1."
        )
        output_fields.add_argument(
            '--out-fields', '-O',
            help="A comma separated list of fields to put in the output."
        )
        output_fields.add_argument(
            '--show-fields', action='store_true', default=False,
            help='Print the available output fields and exit.'
        )
        parser.add_argument(
            '--header', action='store_true', default=False,
            help="Print a header "
        )

        subparsers = parser.add_subparsers(
            dest="list_cmd",
            help="What to list."
        )

        runs_p = subparsers.add_parser(
            'runs',
            aliases=['test_runs', 'tests'],
            help="List test runs.",
            description="Print a list of test run id's."
        )
        filters.add_test_filter_args(runs_p)
        runs_p.add_argument(
            'series', nargs="*",
            help="Print only test runs from these series."
        )

        subparsers.add_parser(
            'series',
            help="List test series.",
            description="Give a list of test series id's."
        )

    def run(self, pav_cfg, args):
        """Find """

        if args.limit in ('none', 'all'):
            args.limit = None
        else:
            try:
                args.limit = int(args.limit)
            except ValueError:
                output.fprint(
                    "Invalid 'limit' option: '{}'".format(args.limit),
                    color=output.RED, file=self.errfile)
                self._parser.print_help(file=self.errfile)
                raise errno.EINVAL

        if args.list_cmd is None:
            output.fprint("Invalid command '{}'.".format(args.list_cmd),
                          color=output.RED, file=self.errfile)
            self._parser.print_help(file=self.errfile)
            return errno.EINVAL

        cmd_name = args.list_cmd

        if cmd_name not in self.sub_cmds:
            raise RuntimeError("Invalid list cmds '{}'".format(cmd_name))

        cmd_result = self.sub_cmds[cmd_name](self, pav_cfg, args)
        return 0 if cmd_result is None else cmd_result

    RUN_LONG_FIELDS = ['id', 'name', 'user', 'sys_name', 'result']

    @sub_cmd(['test_runs', 'tests'])
    def runs_cmd(self, pav_cfg, args):
        """
        :param pav_cfg:
        :param args:
        :return:
        """

        if args.show_fields:
            for field in TestAttributes.list_attrs():
                output.fprint(field, '-', TestAttributes.attr_doc(field))
            return 0

        fields = self.RUN_LONG_FIELDS
        if args.out_fields:
            avail_fields = TestAttributes.list_attrs()
            fields = [field.strip() for field in args.out_fields.split(',')]
            for field in fields:
                if field not in avail_fields:
                    output.fprint(
                        "Invalid output field '{}'. See 'pav list run "
                        "--list-fields.".format(field))
            args.long = True

        filter_func = filters.make_test_run_filter(
            complete=args.complete,
            failed=args.failed,
            incomplete=args.incomplete,
            name=args.name,
            newer_than=args.newer_than,
            older_than=args.older_than,
            passed=args.passed,
            show_skipped=args.show_skipped,
            sys_name=args.sys_name,
            user=args.user,
        )

        order_func, sort_asc = filters.make_test_sort_func(args.sort_by)

        if args.series:
            all_runs = []
            for series_id in args.series:
                try:
                    all_runs.extend(TestSeries.list_series_tests(
                        pav_cfg=pav_cfg,
                        sid=series_id))
                except TestSeriesError as err:
                    output.fprint(
                        "Invalid test series '{}'.\n{}"
                        .format(series_id, err.args[0]),
                        color=output.RED, file=self.errfile)
                    return errno.EINVAL
        else:
            all_runs = dir_db.select(pav_cfg.working_dir/'test_runs')

        runs = dir_db.select_from(
            paths=all_runs,
            transform=TestAttributes,
            filter_func=filter_func,
            order_func=order_func,
            order_asc=sort_asc,
            limit=args.limit,
        )

        rows = [run.as_dict() for run in runs]

        output.draw_table(
            outfile=self.outfile,
            fields=fields,
            rows=rows,
            header=args.header,
            border_chars={'vsep': ' '},
        )

        return 0

    SERIES_LONG_FIELDS = ['id', 'user', 'created', 'num_tests']

    @sub_cmd()
    def series_cmd(self, pav_cfg, args):
        """Print info on each series."""

        series_attrs = {
            'sid': "The series id",
            'user': "The user that created the series.",
            'created': "When the series was created.",
            'num_tests': "Number of tests in the series.",
        }

        if args.show_fields:
            for field, doc in series_attrs.items():
                output.fprint(field, '-', doc)
            return 0

        fields = self.SERIES_LONG_FIELDS if args.long else ['sid']
        if args.out_fields:
            fields = [field.strip() for field in args.out_fields.split(',')]
            for field in fields:
                if field not in series_attrs:
                    output.fprint(
                        "Unknown output field '{}'. See 'pav list series "
                        "--show-fields'".format(field))
                    return errno.EINVAL

        series = []
        series_dirs = dir_db.select(pav_cfg.working_dir/'series')
        for series_dir in series_dirs:
            stat = series_dir.stat()
            created = datetime.datetime.fromtimestamp(stat.st_mtime)
            try:
                user = pwd.getpwuid(stat.st_uid).pw_name
            except KeyError:
                user = '<{}>'.format(stat.st_uid)
            num_tests = len(dir_db.select(series_dir))

            series.append({
                'sid': TestSeries.path_to_sid(series_dir),
                'created': created,
                'user': user,
                'num_tests': num_tests
            })

        series = series[:args.limit]

        output.draw_table(
            outfile=self.outfile,
            fields=fields,
            rows=series,
            border_chars={'hsep': ' '}
        )
