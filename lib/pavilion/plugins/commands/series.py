import subprocess
import os
import json

from pavilion import commands
from pavilion import arguments
from pavilion import series
from pavilion import output
from pavilion import series_config
from pavilion.output import fprint
from pavilion.test_config.resolver import TestConfigResolver
from pavilion.series_config.file_format import SeriesConfigLoader


class RunSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='series',
            description='Run Series.',
            short_help='Run complicated series.',
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            'series_name', action='store',
            help="Series name."
        )
        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')

    def run(self, pav_cfg, args):

        # load series and test files
        series_cfg = series_config.load_series_configs(pav_cfg,
                                                       args.series_name,
                                                       args.modes,
                                                       args.host)

        series_obj = series.TestSeries(pav_cfg,
                                       series_config=series_cfg)

        # check for circular dependencies and create dependencies tree
        series_obj.create_dependency_tree()

        series_path = series_obj.path
        series_id = series_obj._id

        # write dependency tree and config in series dir
        # TODO: make sure this is atomic???
        from pavilion import output
        output.dbg_print(series_obj.dep_graph)
        try:
            with open(str(series_path/'dependency'), 'w') as dep_file:
                dep_file.write(json.dumps(series_obj.dep_graph))
        except FileNotFoundError:
            fprint("Could not write dependency tree to file. Cancelling.",
                   color=output.RED)

        try:
            with open(str(series_path/'config'), 'w') as config_file:
                config_file.write(json.dumps(series_cfg))
        except FileNotFoundError:
            fprint("Could not write series config to file. Cancelling.",
                   color=output.RED)

        # pav _series runs in background using subprocess
        temp_args = ['pav', '_series', str(series_id)]
        try:
            with open(str(series_path/'series.out'), 'w') as series_out:
                series_proc = subprocess.Popen(temp_args,
                                               stdout=series_out,
                                               stderr=series_out)
        except TypeError:
            series_proc = subprocess.Popen(temp_args,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            fprint("Could not kick off tests. Cancelling.",
                   color=output.RED)
            return

        # write pgid to a series file and tell the user how to kill series
        series_pgid = os.getpgid(series_proc.pid)
        try:
            with open(str(series_path/'series.pgid'), 'w') as series_id_file:
                series_id_file.write(str(series_pgid))

            fprint("Started series s{}. "
                   "Run `pav status s{}` to view status. "
                   "PGID is {}. "
                   "To kill, use `kill -15 -{}` or `pav cancel s{}`."
                   .format(series_obj._id,
                           series_obj._id,
                           series_pgid,
                           series_pgid,
                           series_obj._id))
        except TypeError:
            fprint("Warning: Could not write series PGID to a file.",
                   color=output.YELLOW)
            fprint("Started series s{}."
                   "Run `pav status s{}` to view status. "
                   "PGID is {}."
                   "To kill, use `kill -15 -s{}`."
                   .format(series_obj._id,
                           series_obj._id,
                           series_pgid,
                           series_pgid))

        return

