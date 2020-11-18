"""This is the core pavilion script.
It shouldn't be run directly; use bin/pav instead."""

import logging
import os
import sys
import traceback

from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import log_setup
from pavilion import output
from pavilion import pavilion_variables
from pavilion import plugins
from pavilion import permissions

try:
    import yc_yaml
except ImportError:
    output.fprint(
        "Could not find python module 'yc_yaml'. Did you run "
        "`submodule update --init --recursive` to get all the dependencies?"
    )

try:
    import yaml_config
except ImportError:
    output.fprint(
        "Could not find python module 'yaml_config'. Did you run "
        "`submodule update --init --recursive` to get all the dependencies?"
    )


def main():
    """Setup Pavilion and run a command."""

    # Pavilion is compatible with python >= 3.4
    if sys.version_info[0] != 3 or sys.version_info[1] < 5:
        output.fprint("Pavilion requires python 3.5 or higher.",
                      color=output.RED,
                      file=sys.stderr)
        sys.exit(-1)

    # This has to be done before we initialize plugins
    parser = arguments.get_parser()

    # Get the config, and
    try:
        pav_cfg = config.find()
    except Exception as err:
        output.fprint(
            "Error getting config, exiting: {}"
            .format(err),
            file=sys.stderr,
            color=output.RED)
        sys.exit(-1)

    # Create the basic directories in the working directory and the .pavilion
    # directory.
    perm_man = permissions.PermissionsManager(None, pav_cfg['shared_group'],
                                              pav_cfg['umask'])
    for path in [
            config.USER_HOME_PAV,
            config.USER_HOME_PAV/'working_dir',
            pav_cfg.working_dir/'builds',
            pav_cfg.working_dir/'series',
            pav_cfg.working_dir/'test_runs',
            pav_cfg.working_dir/'users']:
        try:
            path = path.expanduser()
            path.mkdir(exist_ok=True)
            perm_man.set_perms(path)
        except OSError as err:
            output.fprint(
                "Could not create base directory '{}': {}"
                .format(path, err),
                color=output.RED,
                file=sys.stderr,
            )
            sys.exit(1)

    # Setup all the loggers for Pavilion
    if not log_setup.setup_loggers(pav_cfg):
        sys.exit(1)

    # Initialize all the plugins
    try:
        plugins.initialize_plugins(pav_cfg)
    except plugins.PluginError as err:
        output.fprint(
            "Error initializing plugins: {}"
            .format(err),
            color=output.RED,
            file=sys.stderr)
        sys.exit(-1)

    # Parse the arguments
    try:
        args = parser.parse_args()
    except Exception:
        raise

    if args.command_name is None:
        parser.print_help()
        sys.exit(0)

    pav_cfg.pav_vars = pavilion_variables.PavVars()

    if not args.profile:
        run_cmd(pav_cfg, args)

    else:
        import cProfile
        import pstats

        stats_path = '/tmp/{}_pav_pstats'.format(os.getlogin())

        cProfile.runctx('run_cmd(pav_cfg, args)', globals(), locals(),
                        stats_path)
        stats = pstats.Stats(stats_path)
        print("Profile Table")
        stats.strip_dirs().sort_stats(args.profile_sort)\
             .print_stats(args.profile_count)

def run_cmd(pav_cfg, args):

    try:
        cmd = commands.get_command(args.command_name)
    except KeyError:
        output.fprint(
            "Unknown command '{}'."
            .format(args.command_name),
            color=output.RED,
            file=sys.stderr)
        sys.exit(-1)

    try:
        sys.exit(cmd.run(pav_cfg, args))
    except KeyboardInterrupt:
        sys.exit(-1)
    except Exception as err:
        exc_info = {
            'traceback': traceback.format_exc(),
            'args': vars(args),
            'config': pav_cfg,
        }

        json_data = output.json_dumps(exc_info)
        logger = logging.getLogger('exceptions')
        logger.error(json_data)

        output.fprint(
            "Unknown error running command {}: {}."
            .format(args.command_name, err),
            color=output.RED,
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)

        output.fprint(
            "Traceback logged to {}".format(pav_cfg.exception_log),
            color=output.RED,
            file=sys.stderr,
        )
        sys.exit(-1)


if __name__ == '__main__':
    main()
