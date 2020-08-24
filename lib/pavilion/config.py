"""This module defines the base configuration for Pavilion itself."""

import grp
import logging
import os
import socket
import sys
from pathlib import Path

import pavilion.output
import yaml_config as yc

LOGGER = logging.getLogger('pavilion.' + __file__)


# Figure out what directories we'll search for configuration files.
PAV_CONFIG_SEARCH_DIRS = [Path('./').resolve()]

try:
    USER_HOME_PAV = (Path('~')/'.pavilion').expanduser()
except OSError:
    # I'm not entirely sure this is the right error to catch.
    USER_HOME_PAV = Path('/tmp')/os.getlogin()/'.pavilion'

PAV_CONFIG_SEARCH_DIRS.append(USER_HOME_PAV)

PAV_CONFIG_DIR = os.environ.get('PAV_CONFIG_DIR', None)

if PAV_CONFIG_DIR is not None:
    PAV_CONFIG_DIR = Path(PAV_CONFIG_DIR)

    if PAV_CONFIG_DIR.exists():
        PAV_CONFIG_SEARCH_DIRS.append(
            Path(PAV_CONFIG_DIR)
        )
    else:
        pavilion.output.fprint(
            "Invalid path in env var PAV_CONFIG_DIR: '{}'. Ignoring."
            .format(PAV_CONFIG_DIR),
            color=pavilion.output.YELLOW,
            file=sys.stderr
        )

PAV_ROOT = Path(__file__).resolve().parents[2]

# Use this config file, if it exists.
PAV_CONFIG_FILE = os.environ.get('PAV_CONFIG_FILE', None)


class ExPathElem(yc.PathElem):
    """Expand environment variables in the path."""

    def validate(self, value, partial=False):
        """Expand environment variables in the path."""

        path = super().validate(value, partial=partial)

        if path is None:
            return None
        elif isinstance(path, str):
            path = Path(path)

        path = Path(os.path.expandvars(path.as_posix()))
        path = path.expanduser()
        return path


def config_dirs_validator(config, values):
    """Get all of the configurations directories and convert them
    into path objects."""

    config_dirs = []

    if config['user_config'] and USER_HOME_PAV and USER_HOME_PAV.exists():
        config_dirs.append(USER_HOME_PAV.resolve())

    if PAV_CONFIG_DIR is not None and PAV_CONFIG_DIR.exists():
        config_dirs.append(PAV_CONFIG_DIR.resolve())

    for value in values:
        path = Path(value)
        if not path.exists():
            pavilion.output.fprint(
                "Config directory {} does not exist. Ignoring."
                .format(value),
                file=sys.stderr,
                color=pavilion.output.YELLOW
            )
        elif path not in config_dirs:
            path = path.resolve()
            config_dirs.append(path)

    return config_dirs


def _group_validate(_, group):
    """Make sure the group specified in the config exists and the user is
    in it."""

    if group is None:
        return

    try:
        group_info = grp.getgrnam(group)
    except KeyError:
        raise ValueError("Group {} is not known on host {}."
                         .format(group, socket.gethostname()))

    user = os.environ['USER']

    if user not in group_info.gr_mem:
        raise ValueError("User '{}' is not in the group '{}'"
                         .format(user, group_info.gr_mem))

    return group


class PavilionConfigLoader(yc.YamlConfigLoader):
    """This object uses YamlConfig to define Pavilion's base configuration
    format and options. If you're looking to add an option to the general
    pavilion.yaml format, this is the place to do it."""

    # Each and every configuration element needs to either not be required,
    # or have a sensible default. Essentially, Pavilion needs to work if no
    # config is given.
    ELEMENTS = [
        yc.ListElem(
            "config_dirs",
            sub_elem=ExPathElem(),
            post_validator=config_dirs_validator,
            help_text="Additional Paths to search for Pavilion config files. "
                      "Pavilion configs (other than this core config) are "
                      "searched for in the given order. In the case of "
                      "identically named files, directories listed earlier "
                      "take precedence."),
        yc.BoolElem(
            "user_config",
            default=False,
            help_text="Whether to automatically add the user's config "
                      "directory at ~/.pavilion to the config_dirs. Configs "
                      "in this directory always take precedence."
        ),
        ExPathElem(
            'working_dir', default=USER_HOME_PAV/'working_dir', required=True,
            help_text="Where pavilion puts it's run files, downloads, etc."),
        yc.ListElem(
            "disable_plugins", sub_elem=yc.StrElem(),
            help_text="Allows you to disable plugins by '<type>.<name>'. For "
                      "example, 'module.gcc' would disable the gcc module "
                      "wrapper."),
        yc.StrElem(
            "shared_group", post_validator=_group_validate,
            help_text="Pavilion can automatically set group permissions on all "
                      "created files, so that users can share relevant "
                      "results, etc."),
        yc.StrElem(
            "umask", default="2",
            help_text="The umask to apply to all files created by pavilion. "
                      "This should be in the format needed by the umask shell "
                      "command."),
        yc.IntRangeElem(
            "build_threads", default=4, vmin=1,
            help_text="Maximum simultaneous builds. Note that each build may "
                      "itself spawn off threads/processes, so it's probably "
                      "reasonable to keep this at just a few."),
        yc.StrElem(
            "log_format",
            default="{asctime}, {levelname}, {hostname}, {name}: {message}",
            help_text="The log format to use for the pavilion logger. "
                      "Uses the modern '{' format style. See: "
                      "https://docs.python.org/3/library/logging.html#"
                      "logrecord-attributes"),
        yc.StrElem(
            "log_level", default="info",
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            help_text="The minimum log level for messages sent to the pavilion "
                      "logfile."),
        ExPathElem(
            "result_log",
            # Derive the default from the working directory, if a value isn't
            # given.
            post_validator=(lambda d, v: v if v is not None else
                            d['working_dir']/'results.log'),
            help_text="Results are put in both the general log and a specific "
                      "results log. This defaults to 'results.log' in the "
                      "working directory."),
        yc.BoolElem(
            "flatten_results", default=True,
            help_text="Flatten results with multiple 'per_file' values into "
                      "multiple result log lines, one for each 'per_file' "
                      "value. Each flattened result will have a 'file' key, "
                      "and the contents of its 'per_file' data will be added "
                      "to the base results mapping."),
        ExPathElem(
            'exception_log',
            # Derive the default from the working directory, if a value isn't
            # given.
            post_validator=(lambda d, v: v if v is not None else
                            d['working_dir']/'exceptions.log'),
            help_text="Full exception tracebacks and related debugging "
                      "information is logged here."
        ),
        yc.IntElem(
            "wget_timeout", default=5,
            help_text="How long to wait on web requests before timing out. On "
                      "networks without internet access, zero will allow you "
                      "to spot issues faster."
        ),
        yc.CategoryElem(
            "proxies", sub_elem=yc.StrElem(),
            help_text="Proxies, by protocol, to use when accessing the "
                      "internet. Eg: http: 'http://myproxy.myorg.org:8000'"),
        yc.ListElem(
            "no_proxy", sub_elem=yc.StrElem(),
            help_text="A list of DNS suffixes to ignore for proxy purposes. "
                      "For example: 'blah.com' would match 'www.blah.com', but "
                      "not 'myblah.com'."),
        yc.ListElem(
            "env_setup", sub_elem=yc.StrElem(),
            help_text="A list of commands to be executed at the beginning of "
                      "every kickoff script."),
        yc.CategoryElem(
            "default_results", sub_elem=yc.StrElem(),
            help_text="Each of these will be added as a constant result "
                      "parser with the corresponding key and constant value. "
                      "Generally, the values should contain a pavilion "
                      "variable of some sort to resolve."),

        # The following configuration items are for internal use and provide a
        # convenient way to pass around core pavilion components or data.
        # They are not intended to be set by the user, and will generally be
        # overwritten without even checking for user provided values.
        ExPathElem(
            'pav_cfg_file', hidden=True,
            help_text="The location of the loaded pav config file."
        ),
        ExPathElem(
            'pav_root', default=PAV_ROOT, hidden=True,
            help_text="The root directory of the pavilion install. This "
                      "shouldn't be set by the user."),
        yc.KeyedElem(
            'pav_vars', elements=[], hidden=True, default={},
            help_text="This will contain the pavilion variable dictionary."),
    ]


def find(target=None, warn=True):
    """Search for a pavilion.yaml configuration file. Use the one pointed
to by the PAV_CONFIG_FILE environment variable. Otherwise, use the first
found in these directories the default config search paths:

- The given 'target' file (used only for testing).
- The ~/.pavilion directory
- The Pavilion source directory (don't put your config here).
"""

    for path in target, PAV_CONFIG_FILE:
        if path is not None:
            pav_cfg_file = Path(path)
            # pylint has a bug that pops up occasionally with pathlib.
            if pav_cfg_file.is_file():  # pylint: disable=no-member
                try:
                    cfg = PavilionConfigLoader().load(
                        pav_cfg_file.open())  # pylint: disable=no-member
                    cfg.pav_cfg_file = pav_cfg_file
                    return cfg
                except Exception as err:
                    raise RuntimeError("Error in Pavilion config at {}: {}"
                                       .format(pav_cfg_file, err))

    for config_dir in PAV_CONFIG_SEARCH_DIRS:
        path = config_dir/'pavilion.yaml'
        if path.is_file():  # pylint: disable=no-member
            try:
                # Parse and load the configuration.
                cfg = PavilionConfigLoader().load(
                    path.open())  # pylint: disable=no-member
                cfg.pav_cfg_file = path
                return cfg
            except Exception as err:
                raise RuntimeError("Error in Pavilion config at {}: {}"
                                   .format(path, err))

    if warn:
        LOGGER.warning("Could not find a pavilion config file. Using an "
                       "empty/default config.")
    return PavilionConfigLoader().load_empty()


def get_version():
    """Returns the current version of Pavilion."""
    version_path = PAV_ROOT / 'RELEASE.txt'

    try:
        with version_path.open() as file:
            lines = file.readlines()
            for line in lines:
                if line.startswith('RELEASE='):
                    return line.split('=')[1].strip()

            return '<unknown>'

    except FileNotFoundError:
        return '<unknown>'
