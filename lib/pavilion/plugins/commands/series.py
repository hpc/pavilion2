import subprocess
import os
import json

from pavilion import commands
from pavilion import arguments
from pavilion import series
from pavilion import output
from pavilion.output import fprint
from pavilion.test_config.resolver import TestConfigResolver
from pavilion.test_config.file_format import SeriesConfigLoader


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

    def run(self, pav_cfg, args):

        # load series and test files
        series_config_loader = SeriesConfigLoader()
        test_config_resolver = TestConfigResolver(pav_cfg)

        # pylint: disable=protected-access
        series_file_path = test_config_resolver._find_config('series',
                                                             args.series_name)

        try:
            with series_file_path.open() as series_file:
                series_cfg = series_config_loader.load(series_file)

                # make series object
                series_obj = series.TestSeries(pav_cfg,
                                               series_config=series_cfg)

                for set_name, set_dict in series_cfg['series'].items():
                    all_modes = series_cfg['modes'] + set_dict['modes']
                    test_config_resolver.load(
                        set_dict['tests'],
                        None,
                        all_modes,
                        None
                    )
        except AttributeError as err:
            fprint("Cannot load series. {}".format(err), color=output.RED)

        # apply ordered: True before checking for dependencies
        if series_cfg['ordered'] in ['True', 'true']:
            ser_keys = list(series_cfg['series'].keys())
            for ser_idx in range(len(ser_keys)-1):
                temp_depends_on = series_cfg['series'][ser_keys[ser_idx+1]][
                    'depends_on']
                if ser_keys[ser_idx] not in temp_depends_on:
                    temp_depends_on.append(ser_keys[ser_idx])

        # check for circular dependencies and create dependencies tree
        series_obj.create_dependency_tree()

        series_path = series_obj.path
        series_id = series_obj._id

        # write dependency tree and config in series dir
        # TODO: make sure this is atomic???
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

            fprint("Started series {}. "
                   "Run `pav status {}` to view status. "
                   "PGID is {}. "
                   "To kill, use `kill -15 -{}` or `pav cancel {}`."
                   .format(series_obj.id,
                           series_obj.id,
                           series_pgid,
                           series_pgid,
                           series_obj.id))
        except TypeError:
            fprint("Warning: Could not write series PGID to a file.",
                   color=output.YELLOW)
            fprint("Started series {}."
                   "Run `pav status {}` to view status. "
                   "PGID is {}."
                   "To kill, use `kill -15 -{}`."
                   .format(series_obj.id,
                           series_obj.id,
                           series_pgid,
                           series_pgid))

        return

