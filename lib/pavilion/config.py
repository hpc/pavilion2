####################################################################
#
#  Disclaimer and Notice of Copyright
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC.
#  This software was produced under U.S. Government contract
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL),
#  which is operated by Los Alamos National Security, LLC for
#  the U.S. Department of Energy. The U.S. Government has rights
#  to use, reproduce, and distribute this software.  NEITHER
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to
#  produce derivative works, such modified software should be
#  clearly marked, so as not to confuse it with the version
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary
#  forms, with or without modification, are permitted provided
#  that the following conditions are met:
#  -  Redistributions of source code must retain the
#     above copyright notice, this list of conditions
#     and the following disclaimer.
#  -  Redistributions in binary form must reproduce the
#     above copyright notice, this list of conditions
#     and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#  -  Neither the name of Los Alamos National Security, LLC,
#     Los Alamos National Laboratory, LANL, the U.S. Government,
#     nor the names of its contributors may be used to endorse
#     or promote products derived from this software without
#     specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
#  OF SUCH DAMAGE.
#
#  ###################################################################

# This module contains the base configuration for Pavilion itself.

import grp
import yaml_config as yc
import os
import socket
import logging

LOGGER = logging.getLogger('pavilion.' + __file__)


def group_validate(_, group):
    """Make sure the group specified in the config exists and the user is
    in it."""

    if group is None:
        return

    try:
        gid = grp.getgrnam(group)
    except KeyError:
        raise ValueError("Group {} is not known on host {}."
                         .format(group, socket.gethostname()))

    if gid not in os.getgroups():
        raise ValueError("Group {} is not in the current user's list of "
                         "groups.".format(group))

    return group


def log_level_validate(_, level):
    """Convert a text log level into a level from the logging module, and
    validate the levels."""

    level = level.lower()
    if level == 'debug':
        return logging.DEBUG
    elif level == 'info':
        return logging.INFO
    elif level == 'warning':
        return logging.WARNING
    elif level == 'error':
        return logging.ERROR
    elif level == 'critical':
        return logging.CRITICAL
    else:
        raise ValueError("Invalid logging level: {}".format(level))


# Figure out what directories we'll search for configuration files.
PAV_CONFIG_SEARCH_DIRS = ['./']

if 'HOME' in os.environ:
    USER_HOME_PAV = os.path.join(os.environ['HOME'], '.pavilion')
    PAV_CONFIG_SEARCH_DIRS.append(USER_HOME_PAV)
else:
    USER_HOME_PAV = None

# Include the pavilion source directory.
PAV_CONFIG_SEARCH_DIRS.append(os.path.dirname(__file__))

if 'PAV_CONFIG_DIR' in os.environ:
    PAV_CONFIG_SEARCH_DIRS.append(os.environ['PAV_CONFIG_DIR'])

PAV_CONFIG_SEARCH_DIRS.extend([
    '/etc/pavilion',
    '/opt/pavilion',
])

dirname = os.path.dirname
pav_root = dirname(dirname(dirname(os.path.realpath(__file__))))


class PavilionConfigLoader(yc.YamlConfigLoader):

    # Each and every configuration element needs to either not be required,
    # or have a sensible default. Essentially, Pavilion needs to work if no
    # config is given.
    ELEMENTS = [
        yc.ListElem(
            "config_dirs",
            defaults=PAV_CONFIG_SEARCH_DIRS,
            sub_elem=yc.StrElem(),
            help_text="Paths to search for Pavilion config files. Pavilion "
                      "configs (other than this core config) are searched for "
                      "in the given order. In the case of identically named "
                      "files, directories listed earlier take precedent."),
        yc.StrElem(
            'working_dir', default=USER_HOME_PAV,
            help_text="Where pavilion puts it's run files, downloads, etc."),
        yc.ListElem(
            "disable_plugins", sub_elem=yc.StrElem(),
            help_text="Allows you to disable plugins by '<type>.<name>'. For "
                      "example, 'module.gcc' would disable the gcc module "
                      "wrapper."),
        yc.StrElem(
            "shared_group", post_validator=group_validate,
            help_text="Pavilion can automatically set group permissions on all "
                      "created files, so that users can share relevant "
                      "results, etc."),
        yc.StrElem(
            "umask", default="0002",
            help_text="The umask to apply to all files created by pavilion. "
                      "This should be in the format needed by the umask shell "
                      "command."),
        yc.StrElem(
            "log_format",
            default="%{asctime}, ${levelname}, ${name}: ${message}",
            help_text="The log format to use for the pavilion logger. See: "
                      "https://docs.python.org/3/library/logging.html#"
                      "logrecord-attributes"),
        yc.StrElem(
            "log_level", default="info", post_validator=log_level_validate,
            help_text="The minimum log level for messages sent to the pavilion "
                      "logfile."),
        yc.IntElem(
            "wget_timeout", default=5,
            help_text="How long to wait on web requests before timing out. On"
                      "networks without internet access, zero will allow you"
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

        # The following configuration items are for internal use and provide a
        # convenient way to pass around core pavilion components or data.
        # They are not intended to be set by the user, and will generally be
        # overwritten without even checking for user provided values.
        yc.StrElem(
            'pav_root', default=pav_root, hidden=True,
            help_text="The root directory of the pavilion install. This "
                      "shouldn't be set by the user."),
        yc.KeyedElem(
            'sys_vars', elements=[], hidden=True, default={},
            help_text="This will contain the system variable dictionary."),
        yc.KeyedElem(
            'pav_vars', elements=[], hidden=True, default={},
            help_text="This will contain the pavilion variable dictionary."),
    ]


def find():
    """Search for a pavilion.yaml configuration file. The first one found is 
    used. Directories are searched in this order: {}
    """.format(PAV_CONFIG_SEARCH_DIRS)

    for config_dir in PAV_CONFIG_SEARCH_DIRS:
        path = os.path.join(config_dir, 'pavilion.yaml')
        if os.path.os.path.isfile(path):
            try:
                # Parse and load the configuration.
                return PavilionConfigLoader().load(open(path))
            except Exception as err:
                raise RuntimeError("Error in Pavilion config at {}: {}"
                                   .format(path, err))

    LOGGER.warning("Could not find a pavilion config file. Using an "
                   "empty/default config.")
    return PavilionConfigLoader().load_empty()
