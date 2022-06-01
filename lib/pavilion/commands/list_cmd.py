"""A command to (relatively) quickly list tests, series, and other (as yet
undefined) bits."""

import errno
from typing import List

from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion.series.info import SeriesInfo
from pavilion.test_run import TestAttributes
from .base_classes import Command, sub_cmd


class ListCommand(Command):
    """List test runs, series, and other bits."""

    def __init__(self):

        super().__init__(
            name='list',
            aliases=['list_cmd'],
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
        runs_p.add_argument('--label', default=None,
                            help="The config label to search under.")

        filters.add_test_filter_args(runs_p)

        runs_p.add_argument(
            'tests', nargs="*", default=['all'],
            help="Specific tests (or series) to filter from. Defaults to"
                 "'all'."
        )

        series_p = subparsers.add_parser(
            'series',
            help="List test series.",
            description="Give a list of test series id's."
        )

        series_p.add_argument(
            'series', nargs="*", default=['all'],
            help="Specific series to filter from. Defaults to 'all'"
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
                    output.fprint(self.errfile, "Invalid output field '{}'. See 'pav list "
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
            output.fprint(self.errfile, "No matching items found.")
            return 0

        if mode in (self.OUTMODE_SPACE, self.OUTMODE_NEWLINE):
            sep = ' ' if mode == self.OUTMODE_SPACE else '\n'
            for row in rows:
                output.fprint(self.outfile, row[fields[0]], end=sep)
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
                output.fprint(self.outfile, field, '-', TestAttributes.attr_doc(field))
            return 0

        fields, mode = self.get_fields(
            fields_arg=args.out_fields,
            mode_arg=args.output_mode,
            default_single_field='id',
            default_fields=self.RUN_LONG_FIELDS,
            avail_fields=TestAttributes.list_attrs()
        )

        test_runs = cmd_utils.arg_filtered_tests(pav_cfg, args, verbose=self.errfile).data

        for run in test_runs:
            for key, value in list(run.items()):
                if value in [None, '']:
                    del run[key]

        self.write_output(
            mode=mode,
            rows=test_runs,
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
                output.fprint(self.outfile, field, '-', doc)
            return 0

        fields, mode = self.get_fields(
            fields_arg=args.out_fields,
            mode_arg=args.output_mode,
            default_single_field='sid',
            default_fields=self.SERIES_LONG_FIELDS,
            avail_fields=list(series_attrs.keys()),
        )

        series = cmd_utils.arg_filtered_series(pav_cfg, args, verbose=self.errfile)
        series = [dict(series_info) for series_info in series]

        self.write_output(
            mode=mode,
            rows=series,
            fields=fields,
            header=args.header,
            vsep=args.vsep,
            wrap=args.wrap,
        )
