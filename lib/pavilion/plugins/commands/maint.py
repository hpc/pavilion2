"""A command to (relatively) quickly list tests, series, and other (as yet
undefined) bits."""
import errno

import pavilion.result.common
from pavilion import commands
from pavilion import output
from pavilion import result
from pavilion.commands import sub_cmd


class MaintCommand(commands.Command):
    """Perform various maintanance tasks."""

    def __init__(self):

        super().__init__(
            name='maint',
            short_help="Perform various maintenance tasks. See 'pav maint -h'.",
            sub_commands=True,
            description="Various maintenance sub-commands."
        )

    def _setup_arguments(self, parser):

        self._parser = parser

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="The maintenance sub-command."
        )

        result_prune_p = subparsers.add_parser(
            name="result_prune",
            help="Remove matching results from the common result log.",
            aliases=['prune_results', 'prune_result'],
            description=(
                "Remove results with the given ids/uuids from the result log. "
                "WARNING: This will cause changes to the log file that may "
                "case log aggregation engines (namely Splunk) to re-index the "
                "file. This can result in duplicate result log entries in said "
                "engine.")
            # Note: There isn't really any way around this for what we're
            # doing. Splunk tracks a CRC of the beginning of the file and
            # at it's expected seek position.
        )

        result_prune_p.add_argument(
            '--json', action='store_true', default=False,
            help="Print the pruned results as json rather than as a table."
        )
        result_prune_p.add_argument(
            'ids', nargs="+",
            help="Test run ids and/or uuids to prune in the results log."
        )

    def run(self, pav_cfg, args):
        """Find and run the given maint sub-command."""

        return self._run_sub_command(pav_cfg, args)

    @sub_cmd('prune_results', 'prune_result')
    def _result_prune_cmd(self, pav_cfg, args):
        """Remove matching results from the results log."""

        try:
            pruned = result.prune_result_log(pav_cfg.result_log, args.ids)
        except pavilion.result.common.ResultError as err:
            output.fprint(err.args[0], file=self.errfile, color=output.RED)
            return errno.EACCES

        if args.json:
            output.json_dump(
                obj=pruned,
                file=self.outfile,
            )
        else:
            output.draw_table(
                outfile=self.outfile,
                fields=['id', 'uuid', 'name', 'result', 'created'],
                rows=pruned,
                title="Pruned Results"
            )
