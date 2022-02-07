from pavilion import series
from pavilion import filters
from pavilion import output
from pavilion import cmd_utils
from .base_classes import Command, sub_cmd


class SeriesStatus(Command):

    def __init__(self):
        super().__init__(
            'series-status',
            "Commands to give the status of started test series.",
            short_help="Show test series status.",
            aliases=['sstatus'],
            sub_commands=True,
        )

    def _setup_arguments(self, parser):

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="Series Status sub command.")

        list_p = subparsers.add_parser(
            'list',
            aliases=['ls'],
            help="Show a list of recently run series.",
        )

        list_p.add_argument(
            'series', nargs='*',
            help="Specific series to show. Defaults to all your recent series on this cluster."
        )

        filters.add_series_filter_args(list_p)

    @sub_cmd('ls')
    def _list_cmd(self, pav_cfg, args):
        """List series."""

        rows = cmd_utils.arg_filtered_series(
            pav_cfg=pav_cfg, args=args, verbose=self.errfile)

        for row in rows:
            row['pfe'] = '{}/{}/{}'.format(row['passed'], row['failed'], row['errors'])

        output.draw_table(
            outfile=self.outfile,
            fields=['sid', 'status', 'num_tests', 'user', 'sys_name', 'complete', 'pfe'],
            rows=rows,
            field_info={
                'num_tests': {'title': 'Tests'},
                'pfe': {'title': 'P/F/Err'},
            }
        )

        return 0

    def run(self, pav_cfg, args):
        """Run the show command's chosen sub-command."""

        return self._run_sub_command(pav_cfg, args)
