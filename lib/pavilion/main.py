"""This is the core pavilion script.
It shouldn't be run directly; use bin/pav instead."""

import logging
import sys
import traceback

import pavilion.commands
import pavilion.errors
from . import arguments
from . import commands
from . import config
from . import log_setup
from . import output
from . import pavilion_variables
from . import plugins
from . import utils

try:
    import yc_yaml
except ImportError:
    output.fprint(sys.stdout, "Could not find python module 'yc_yaml'. Did you run "
                              "`submodule update --init --recursive` to get all "
                              "the dependencies?")

try:
    import yaml_config
except ImportError:
    output.fprint(sys.stdout, "Could not find python module 'yaml_config'. Did you run "
                              "`submodule update --init --recursive` to get all the "
                              "dependencies?")


# pylint: disable=broad-except
def main():
    """Setup Pavilion and run a command."""

    # Pavilion is compatible with python >= 3.4
    if sys.version_info[0] != 3 or sys.version_info[1] < 5:
        output.fprint(sys.stderr, "Pavilion requires python 3.5 or higher.", color=output.RED)
        sys.exit(-1)

    # This has to be done before we initialize plugins
    parser = arguments.get_parser()

    # Get the config, and
    try:
        pav_cfg = config.find_pavilion_config()
    except Exception as err:
        output.fprint(sys.stderr, "Error getting config, exiting.", err, color=output.RED)
        sys.exit(-1)

    # Setup all the loggers for Pavilion
    if not log_setup.setup_loggers(pav_cfg):
        output.fprint(sys.stderr,
                      "Could not set up loggers. This is usually because of a badly defined "
                      "working_dir in pavilion.yaml.", color=output.RED)
        sys.exit(-1)

    # Initialize all the plugins
    try:
        plugins.initialize_plugins(pav_cfg)
    except pavilion.errors.PluginError as err:
        output.fprint(sys.stderr, "Error initializing plugins.", err, color=output.RED)
        sys.exit(-1)

    # Partially parse the arguments. All we really care about is the subcommand.
    partial_args, _ = parser.parse_known_args()

    # If there is no subcommand, just print help. This also applies when the user
    # asks for help with --help/-h.  Sub-command help will trigger when we parse the full
    # args.
    if partial_args.command_name is None:
        # Load all the commands (and add their arguments) before displaying help.
        commands.load()
        parser.print_help()
        sys.exit(1)

    # We find the command twice. The first time module loads it if necessary
    # (builtin commands are lazily loaded).
    commands.get_command(partial_args.command_name)

    # Now that we've loaded the command (which adds its subparser to the main
    # parser), we'll reparse the args for real.
    args = parser.parse_args()

    pav_cfg.pav_vars = pavilion_variables.PavVars()
    run_cmd(pav_cfg, args)


def run_cmd(pav_cfg, args):
    """Run the command specified by the user using the remaining arguments."""

    try:
        cmd = pavilion.commands.get_command(args.command_name)
    except KeyError:
        output.fprint(sys.stderr, "Unknown command '{}'."
                      .format(args.command_name), color=output.RED)
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

        output.fprint(sys.stderr, "Unknown error running command {}."
                      .format(args.command_name), err, color=output.RED)
        traceback.print_exc(file=sys.stderr)

        output.fprint(sys.stderr, "Traceback logged to {}".format(pav_cfg.exception_log),
                      color=output.RED)
        sys.exit(-1)


def _get_arg_val(arg_name, default):
    """Get the given (long) argument value from sys.argv. We won't have the actual
    argparser up and ready at this point."""

    for i in range(len(sys.argv)):
        arg = sys.argv[i]
        if arg.startswith('--{}='.format(arg_name)):
            return arg.split('=', 1)[1]
        elif arg == '--{}'.format(arg_name) and (i + 1) < len(sys.argv):
            return sys.argv[i + 1]

    return default


def profile_main():
    """Run main, but under the python profiler."""

    # pylint: disable=import-outside-toplevel
    import cProfile
    import pstats

    p_sort = _get_arg_val('profile-sort', arguments.PROFILE_SORT_DEFAULT)
    p_count = _get_arg_val('profile-count', arguments.PROFILE_COUNT_DEFAULT)

    stats_path = '/tmp/{}_pav_pstats'.format(utils.get_login())

    cProfile.runctx('main()', globals(), locals(), stats_path)
    stats = pstats.Stats(stats_path)
    output.fprint(sys.stdout, "Profile Table")
    stats.strip_dirs().sort_stats(p_sort).print_stats(int(p_count))


if __name__ == '__main__':
    if '--profile' in sys.argv:
        profile_main()
    else:
        main()
