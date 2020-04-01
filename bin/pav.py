# This is the core pavilion script.
# It shouldn't be run directly; use bin/pav instead.

import logging
import os
import socket
import sys
import traceback
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import output
from pavilion import pavilion_variables
from pavilion import plugins

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
    # Pavilion is compatible with python >= 3.4
    if sys.version_info[0] != 3 or sys.version_info[1] < 4:
        output.fprint("Pavilion requires python 3.4 or higher.",
                      color=output.RED,
                      file=sys.stderr)
        sys.exit(-1)

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
    for path in [
            config.USER_HOME_PAV,
            config.USER_HOME_PAV/'working_dir',
            pav_cfg.working_dir/'builds',
            pav_cfg.working_dir/'downloads',
            pav_cfg.working_dir/'series',
            pav_cfg.working_dir/'test_runs',
            pav_cfg.working_dir/'users']:
        try:
            path = path.expanduser()
            path.mkdir(exist_ok=True)
        except OSError as err:
            output.fprint(
                "Could not create base directory '{}': {}"
                .format(path, err),
                color=output.RED,
                file=sys.stderr,
            )
            sys.exit(1)

    root_logger = logging.getLogger()

    # Set up a directory for tracebacks.
    tracebacks_dir = Path('~/.pavilion/tracebacks').expanduser()
    tracebacks_dir.mkdir(parents=True, exist_ok=True)

    # Setup the logging records to contain host information, just like in
    # the logging module example
    old_factory = logging.getLogRecordFactory()
    hostname = socket.gethostname()

    def record_factory(*fargs, **kwargs):
        record = old_factory(*fargs, **kwargs)
        record.hostname = hostname
        return record

    # Setup the new record factory.
    logging.setLogRecordFactory(record_factory)

    # Put the log file in the lowest common pav config directory we can write
    # to.
    log_fn = pav_cfg.working_dir/'pav.log'
    # Set up a rotating logfile than rotates when it gets larger
    # than 1 MB.
    try:
        log_fn.touch()
    except (PermissionError, FileNotFoundError) as err:
        output.fprint("Could not write to pavilion log at '{}': {}"
                      .format(log_fn, err),
                      color=output.YELLOW,
                      file=sys.stderr,
                      )
    else:
        file_handler = RotatingFileHandler(filename=str(log_fn),
                                           maxBytes=1024 ** 2,
                                           backupCount=3)
        file_handler.setFormatter(logging.Formatter(pav_cfg.log_format,
                                                    style='{'))
        file_handler.setLevel(getattr(logging,
                                      pav_cfg.log_level.upper()))
        root_logger.addHandler(file_handler)

    # The root logger should pass all messages, even if the handlers
    # filter them.
    root_logger.setLevel(logging.DEBUG)

    # Setup the result logger.
    # Results will be logged to both the main log and the result log.
    try:
        pav_cfg.result_log.touch()
    except (PermissionError, FileNotFoundError) as err:
        output.fprint(
            "Could not write to result log at '{}': {}"
            .format(pav_cfg.result_log, err),
            color=output.YELLOW,
            file=sys.stderr
        )
        sys.exit(1)

    result_logger = logging.getLogger('results')
    result_handler = RotatingFileHandler(filename=str(pav_cfg.result_log),
                                         # 20 MB
                                         maxBytes=20 * 1024 ** 2,
                                         backupCount=3)
    result_handler.setFormatter(logging.Formatter("{message}", style='{'))
    result_logger.setLevel(logging.INFO)
    result_logger.addHandler(result_handler)

    # Setup the exception logger.
    # Exceptions will be logged to this directory, along with other useful info.
    exc_logger = logging.getLogger('exceptions')
    try:
        pav_cfg.exception_log.touch()
    except (PermissionError, FileNotFoundError) as err:
        output.fprint(
            "Could not write to exception log at '{}': {}"
            .format(pav_cfg.exception_log, err),
            color=output.YELLOW,
            file=sys.stderr
        )
    else:
        exc_handler = RotatingFileHandler(
            filename=pav_cfg.exception_log.as_posix(),
            maxBytes=20 * 1024 ** 2,
            backupCount=3,
        )
        exc_handler.setFormatter(logging.Formatter(
            "{asctime} {message}",
            style='{',
        ))
        exc_logger.setLevel(logging.ERROR)
        exc_logger.addHandler(exc_handler)

    # Setup the yapsy logger to log to terminal. We need to know immediatly
    # when yapsy encounters errors.
    yapsy_logger = logging.getLogger('yapsy')
    yapsy_handler = StreamHandler(stream=sys.stderr)
    # Color all these error messages red.
    yapsy_handler.setFormatter(
        logging.Formatter("\x1b[31m{asctime} {message}\x1b[0m",
                          style='{'))
    yapsy_logger.setLevel(logging.INFO)
    yapsy_logger.addHandler(yapsy_handler)

    # This has to be done before we initialize plugins
    parser = arguments.get_parser()

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

    pav_cfg.pav_vars = pavilion_variables.PavVars()

    # Parse the arguments
    try:
        args = parser.parse_args()
    except Exception:
        # TODO: Handle argument parsing errors correctly.
        raise

    # Add a stream to stderr if we're in verbose mode, or if no other handler
    # is defined.
    if args.verbose or not root_logger.handlers:
        verbose_handler = logging.StreamHandler(sys.stderr)
        verbose_handler.setLevel(logging.DEBUG)
        verbose_handler.setFormatter(logging.Formatter(pav_cfg.log_format,
                                                       style='{'))
        root_logger.addHandler(result_handler)

    if args.command_name is None:
        parser.print_help()
        sys.exit(0)

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
