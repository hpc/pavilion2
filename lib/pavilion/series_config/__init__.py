import os
from typing import List

import yc_yaml
from pavilion.test_config.resolver import TestConfigResolver, TestConfigError
from .file_format import SeriesConfigLoader


class SeriesConfigError(RuntimeError):
    """For errors handling series configs."""


def find_all_series(pav_cfg):
    """Find all the series within known config directories.

:return: Returns a dictionary of series names to an info dict.
:rtype: dict(dict)

The returned data structure looks like: ::

    series_name -> {
        'path': Path to the series file.
        'supersedes': [superseded_suite_files],
        'err': errors
        'tests': [test_names]
        }
"""

    series = {}

    for conf_dir in pav_cfg.config_dirs:
        path = conf_dir / 'series'

        if not (path.exists() and path.is_dir()):
            continue

        for file in os.listdir(path.as_posix()):

            file = path / file
            if file.suffix == '.yaml' and file.is_file():
                series_name = file.stem

                if series_name not in series:
                    series[series_name] = {
                        'path': file,
                        'err': '',
                        'tests': [],
                        'supersedes': [],
                    }
                else:
                    suites[suite_name]['supersedes'].append(file)

                with file.open('r') as series_file:
                    try:
                        series_cfg = SeriesConfigLoader().load(
                            series_file, partial=True)
                        series[series_name]['tests'] = list(
                            series_cfg['series'].keys())
                    except (
                            TypeError,
                            KeyError,
                            ValueError,
                            yc_yaml.YAMLError,
                    ) as err:
                        series[series_name]['err'] = err
                        continue

    return series


def load_series_configs(pav_cfg, series_name: str, cl_modes: List[str],
                        cl_host: str) -> dict:
    """Loads series config and checks that all tests can be loaded with all
    modes and host (if any). """

    series_config_loader = SeriesConfigLoader()
    test_config_resolver = TestConfigResolver(pav_cfg)

    series_file_path = test_config_resolver.find_config('series',
                                                        series_name)
    if not series_file_path:
        raise SeriesConfigError('Cannot find series config: {}'.
                                format(args.series_name))

    try:
        with series_file_path.open() as series_file:
            series_cfg = series_config_loader.load(series_file)

            for set_name, set_dict in series_cfg['series'].items():
                all_modes = series_cfg['modes'] + set_dict['modes'] + cl_modes
                test_config_resolver.load(
                    set_dict['tests'],
                    cl_host,
                    all_modes,
                )

            # add modes and host from command line to config
            series_cfg['modes'] = all_modes
            series_cfg['host'] = cl_host
    except AttributeError as err:
        raise SeriesConfigError("Cannot load series. {}".format(err.args[0]))
    except TestConfigError as err:
        raise SeriesConfigError("Error loading test for series {}.\n{}"
                                .format(series_name, err.args[0]))

    return series_cfg
