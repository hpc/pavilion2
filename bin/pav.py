# This is the core pavilion script.
# It shouldn't be run directly; use bin/pav instead.

from logging.handlers import RotatingFileHandler
from logging import StreamHandler
from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import plugins
from pavilion import pav_vars
from pavilion import utils
import logging
from pathlib import Path
import os
import socket
import sys
import traceback

try:
    import yc_yaml
except ImportError:
    utils.fprint(
        "Could not find python module 'yc_yaml'. Did you run "
        "`submodule update --init --recursive` to get all the dependencies?"
    )

try:
    import yaml_config
except ImportError:
    utils.fprint(
        "Could not find python module 'yaml_config'. Did you run "
        "`submodule update --init --recursive` to get all the dependencies?"
    )


def main():
    # Pavilion is compatible with python >= 3.4
    if sys.version_info[0] != 3 or sys.version_info[1] < 4:
        print("Pavilion requires python 3.4 or higher.", file=sys.stderr)
        sys.exit(-1)

    # Get the config, and
    try:
        pav_cfg = config.find()
    except Exception as err:
        print(err, file=sys.stderr)
        sys.exit(-1)

    # Create the basic directories in the working directory
    for path in [
            pav_cfg.working_dir,
            pav_cfg.working_dir/'builds',
            pav_cfg.working_dir/'downloads',
            pav_cfg.working_dir/'series',
            pav_cfg.working_dir/'test_runs',
            pav_cfg.working_dir/'users']:
        if not path.exists():
            try:
                path.mkdir()
            except OSError as err:
                # Handle potential race conditions with directory creation.
                if path.exists():
                    # Something else created the directory
                    pass
                else:
                    print("Could not create base directory '{}': {}"
                          .format(path, err))
                    sys.exit(1)

    root_logger = logging.getLogger()

    # Set up a directory for tracebacks.
    tracebacks_dir = Path(os.path.expanduser('~/.pavilion/tracebacks'))
    os.makedirs(str(tracebacks_dir), exist_ok=True)

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
    result_logger = logging.getLogger('results')
    result_handler = RotatingFileHandler(filename=str(pav_cfg.result_log),
                                         # 20 MB
                                         maxBytes=20 * 1024 ** 2,
                                         backupCount=3)
    result_handler.setFormatter(logging.Formatter("{asctime} {message}",
                                                  style='{'))
    result_logger.setLevel(logging.INFO)
    result_logger.addHandler(result_handler)

    # Setup the exception logger.
    # Exceptions will be logged to this directory, along with other useful info.
    exc_logger = logging.getLogger('exceptions')
    try:
        if not pav_cfg.exception_log.exists():
            pav_cfg.exception_log.parent.mkdir(
                mode=0o775,
                parents=True,
                #exist_ok=True  # Doesn't work in python 3.4 (added in 3.5)
            )
    except (PermissionError, OSError, IOError, FileExistsError) as err:
        utils.dbg_print("Could not create exception log")

    exc_handler = RotatingFileHandler(
        filename=pav_cfg.exception_log.as_posix(),
        maxBytes=20 * 1024 **2,
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
        print("Error initializing plugins: {}".format(err), file=sys.stderr)
        sys.exit(-1)

    pav_cfg.pav_vars = pav_vars.PavVars()

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
        print("Unknown command {}.".format(args.command_name), file=sys.stderr)
        sys.exit(-1)

    try:
        sys.exit(cmd.run(pav_cfg, args))
    except Exception as err:
        exc_info = {
            'traceback': traceback.format_exc(),
            'args': vars(args),
            'config': pav_cfg,
        }

        json_data = utils.json_dumps(exc_info)
        logger = logging.getLogger('exceptions')
        logger.error(json_data)

        utils.fprint(
            "Unknown error running command {}: {}."
            .format(args.command_name, err),
            color=utils.RED,
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)

        utils.fprint(
            "Traceback logged to {}".format(pav_cfg.exception_log),
            color=utils.RED,
            file=sys.stderr,
        )
        sys.exit(-1)


if __name__ == '__main__':
    main()
