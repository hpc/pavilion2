"""A command to (relatively) quickly list tests, series, and other (as yet
undefined) bits."""

import errno
from typing import List

from pavilion import commands
from pavilion import dir_db
from pavilion import filters
from pavilion import output
from pavilion.commands import sub_cmd
from pavilion.series import TestSeries
from pavilion.series_util import SeriesInfo, TestSeriesError, \
    series_info_transform, list_series_tests
from pavilion.test_run import TestAttributes, test_run_attr_transform


class ListCommand(commands.Command):
    """List test runs, series, and other bits."""

    def __init__(self):

        super().__init__(
            name='list',
            short_help="Quickly and compactly list Pavilion test runs or "
                       "series.",
            sub_commands=True,
            description="List test runs or series with minimal information. "
                        "For more detailed info, use 'pav status'. This "
                        "command is for getting a filtered list of tests or "
                        "series that can easily be fed directly to other "
                        "commands. "
                        "By default the output is a separated list of "
                        "items."
        )

    RUN_LONG_FIELDS = ['id', 'name', 'user', 'sys_name', 'result']

    OUTMODE_SPACE = 'space_sep'
    OUTMODE_NEWLINE = 'newline_sep'
    OUTMODE_LONG = 'long'
    OUTMODE_CSV = 'csv'

    # Generic field info for draw_table
    FIELD_INFO = {
        'created':  {'transform': lambda d: d.isoformat()},
        'finished': {'transform': lambda d: d.isoformat()},
        'started':  {'transform': lambda d: d.isoformat()},
    }

    def _setup_arguments(self, parser):

        self._parser = parser

        output_mode = parser.add_mutually_exclusive_group()
        output_mode.add_argument(
            '--multi-line', action='store_const',
            default=self.OUTMODE_SPACE,
            dest='output_mode', const=self.OUTMODE_NEWLINE,
            help="List the results one per line.")
        output_mode.add_argument(
            '--long', '-l', action='store_const',
            dest='output_mode', const=self.OUTMODE_LONG,
            help="Show additional fields, one per line.\n"
                 "Default fields: {}".format(self.RUN_LONG_FIELDS)
        )
        output_mode.add_argument(
            '--csv', action='store_const', const=self.OUTMODE_CSV,
            dest='output_mode', help="Write output as CSV."
        )
        output_mode.add_argument(
            '--show-fields', action='store_true', default=False,
            help='Print the available output fields and exit.'
        )

        parser.add_argument(
            '--out-fields', '-O',
            help="A comma separated list of fields to put in the output. More"
                 "than one field requires '--long' or '--csv' mode. "
                 "See --show-fields for available fields."
        )
        parser.add_argument(
            '--header', action='store_true', default=False,
            help="Print a header when printing in --long or --csv mode."
        )
        parser.add_argument(
            '--vsep', default='|', type=lambda s: s[0],
            help="Vertical separator for --long mode. Single character only."
        )
        parser.add_argument(
            '--wrap', action='store_true', default=False,
            help="Auto-wrap the table columns in long output mode."
        )

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="What to list."
        )

        runs_p = subparsers.add_parser(
            'test_runs',
            aliases=['runs', 'tests'],
            help="List test runs.",
            description="Print a list of test run id's."
        )

        filters.add_test_filter_args(runs_p)

        runs_p.add_argument(
            'series', nargs="*",
            help="Print only test runs from these series."
        )

        series_p = subparsers.add_parser(
            'series',
            help="List test series.",
            description="Give a list of test series id's."
        )

        filters.add_series_filter_args(series_p)

    def run(self, pav_cfg, args):
        """Find the proper subcommand and run it."""

        return self._run_sub_command(pav_cfg, args)

    def get_fields(self, fields_arg: str, mode_arg: str,
                   avail_fields: List[str],
                   default_single_field: str,
                   default_fields: List[str]) -> (List[str], str):
        """Get the fields and updated output mode.

        :param fields_arg: The fields given by the user (if any).
        :param mode_arg: The output mode.
        :param avail_fields: The available fields.
        :param default_single_field: Default field for basic/newline modes.
        :param default_fields: The default fields for long/csv modes.
        :return: The fields list and an updated mode
        """

        fields = []
        if fields_arg:
            fields = [field.strip() for field in fields_arg.split(',')]
            for field in fields:
                if field not in avail_fields:
                    output.fprint(
                        "Invalid output field '{}'. See 'pav list "
                        "--show-fields.".format(field))
                    return errno.EINVAL

        if (len(fields) > 1 and mode_arg not in (self.OUTMODE_LONG,
                                                 self.OUTMODE_CSV)):
            mode_arg = self.OUTMODE_LONG

        if not fields:
            if mode_arg in (self.OUTMODE_LONG, self.OUTMODE_CSV):
                fields = default_fields
            else:
                fields = [default_single_field]

        return fields, mode_arg

    def write_output(self, mode: str, rows: List[dict], fields: List[str],
                     header: bool, vsep: str, wrap: bool):
        """Generically produce the output.
        :param mode: The output mode
        :param rows: Output items
        :param fields: List of fields to display.
        :param header: Whether to display a header in long/cvs mode
        :param vsep: Long mode vertical separator
        :param wrap: Wrap columns in long output mode.
        """

        if not rows:
            output.fprint("No matching items found.", file=self.errfile)
            return 0

        if mode in (self.OUTMODE_SPACE, self.OUTMODE_NEWLINE):
            sep = ' ' if mode == self.OUTMODE_SPACE else '\n'
            for row in rows:
                output.fprint(row[fields[0]], end=sep, file=self.outfile)
            output.fprint(file=self.outfile)

        elif mode == self.OUTMODE_LONG:
            output.draw_table(
                outfile=self.outfile,
                fields=fields,
                field_info=self.FIELD_INFO,
                rows=rows,
                header=header,
                border_chars={'vsep': vsep},
                table_width=None if wrap else 1024**2
            )
        else:  # CSV
            output.output_csv(
                outfile=self.outfile,
                fields=fields,
                rows=rows,
                header=header,
            )

        return 0

    @sub_cmd('runs', 'tests')
    def _test_runs_cmd(self, pav_cfg, args):
        """
        :param pav_cfg:
        :param args:
        :return:
        """

        if args.show_fields:
            for field in TestAttributes.list_attrs():
                output.fprint(field, '-', TestAttributes.attr_doc(field),
                              file=self.outfile)
            return 0

        fields, mode = self.get_fields(
            fields_arg=args.out_fields,
            mode_arg=args.output_mode,
            default_single_field='id',
            default_fields=self.RUN_LONG_FIELDS,
            avail_fields=TestAttributes.list_attrs()
        )

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

        order_func, ascending = filters.get_sort_opts(ßargs.sort_by, "TEST")

        if args.series:
            picked_runs = []
            for series_id in args.series:
                try:
                    picked_runs.extend(list_series_tests(
                        pav_cfg=pav_cfg,
                        sid=series_id))
                except TestSeriesError as err:
                    output.fprint(
                        "Invalid test series '{}'.\n{}"
                        .format(series_id, err.args[0]),
                        color=output.RED, file=self.errfile)
                    return errno.EINVAL
            runs = dir_db.select_from(
                paths=picked_runs,
                transform=test_run_attr_transform,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=ascending,
                limit=args.limit,
            ).data
        else:
            runs = dir_db.select(
                id_dir=pav_cfg.working_dir/'test_runs',
                transform=test_run_attr_transform,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=ascending,
                limit=args.limit,
            ).data

        for run in runs:
            for key, value in list(run.items()):
                if value in [None, '']:
                    del run[key]

        self.write_output(
            mode=mode,
            rows=runs,
            fields=fields,
            header=args.header,
            vsep=args.vsep,
            wrap=args.wrap,
        )

    SERIES_LONG_FIELDS = ['id', 'user', 'created', 'num_tests']

    @sub_cmd()
    def _series_cmd(self, pav_cfg, args):
        """Print info on each series."""

        series_attrs = {
            key: SeriesInfo.attr_doc(key) for key in SeriesInfo.list_attrs()}

        if args.show_fields:
            for field, doc in series_attrs.items():
                output.fprint(field, '-', doc, file=self.outfile)
            return 0

        fields, mode = self.get_fields(
            fields_arg=args.out_fields,
            mode_arg=args.output_mode,
            default_single_field='sid',
            default_fields=self.SERIES_LONG_FIELDS,
            avail_fields=list(series_attrs.keys()),
        )

        series_filter = filters.make_series_filter(
            complete=args.complete,
            incomplete=args.incomplete,
            newer_than=args.newer_than,
            older_than=args.older_than,
            sys_name=args.sys_name)

        series_order, ascending = filters.get_sort_opts(args.sort_by,"SERIES")

        series = dir_db.select(
            id_dir=pav_cfg.working_dir/'series',
            filter_func=series_filter,
            transform=series_info_transform,
            order_func=series_order,
            order_asc=ascending,
        ).data
        self.write_output(
            mode=mode,
            rows=series,
            fields=fields,
            header=args.header,
            vsep=args.vsep,
            wrap=args.wrap,
        )
