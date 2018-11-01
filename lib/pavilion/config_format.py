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

from __future__ import division, unicode_literals, print_function
import pavilion.dependencies.yaml_config as yc
import re


class TestConfigError(ValueError):
    """An exception specific to errors in configuration."""
    pass


KEY_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]+$')


class VariableElem(yc.CategoryElem):
    """A variable entry can be either a single string value or a dictionary of values. If we get
    a single value, we'll return it instead of a dict."""

    _NAME_RE = KEY_NAME_RE

    def __init__(self, name=None, **kwargs):
        """Just like a CategoryElem, but we force some of the params."""
        super(VariableElem, self).__init__(name=name,
                                           sub_elem=yc.StrElem(),
                                           defaults=None,
                                           **kwargs)

    def validate(self, value_dict):
        """Check for a single item and return it, otherwise return a dict."""

        if isinstance(value_dict, str):
            return value_dict

        return super(VariableElem, self).validate(value_dict)


class VarCatElem(yc.CategoryElem):
    """Just like a regular category elem, but we override the key regex to allow dashes. We
    won't be using name style references anyway."""
    _NAME_RE = KEY_NAME_RE


class TestConfigLoader(yc.YamlConfigLoader):
    """This class describes a test section in a Pavilion config file. It is expected to be
    added to by various plugins."""


    # DEV NOTE:


    ELEMENTS = [
        yc.RegexElem('inherits_from', regex=r'\w+',
                     help_text="Inherit from the given test section, and override parameters with"
                               "those specified in this one. Lists are overridden entirely"),
        yc.StrElem('subtitle',
                   help_text="An extended title for this test. This is useful for assigning a "
                             "unique name to virtual tests through variable insertion. For "
                             "example, if a test has a single permutation variable named "
                             "'subtest', then '{subtest}' would give a useful descriptor."),
        VarCatElem('variables', sub_elem=yc.ListElem(sub_elem=VariableElem()),
                   help_text="Variables for this test section. These can be inserted into "
                             "strings anywhere else in the config through the string formatting "
                             "syntax. They keys 'var', 'per', 'pav', 'sys' and 'sched' are "
                             "reserved. Each value may be a single or list of strings or "
                             "key/string pairs."),
        VarCatElem('permutations', sub_elem=yc.ListElem(sub_elem=VariableElem()),
                   help_text="Permutation variables for this test section. These are just like "
                             "normal variables, but they if a list of values (whether a single "
                             "string or key/string pairs) is given, then a virtual test is "
                             "created for each combination across all variables in each section. "
                             "The resulting virtual test is thus given a single permutation of "
                             "these values."),
        yc.RegexElem('scheduler', regex=r'\w+',
                     help_text="The scheduler class to use to run this test."),
        yc.KeyedElem('build', elements=[
            yc.StrElem('source_location',
                       help_text="Path to the test source. It may be a directory, a tar file, "
                                 "or a git URI. If it's a directory or file, the path is relative "
                                 "to '$PAV_CONFIG/test_src' by default."),
            yc.ListElem('modules', sub_elem=yc.StrElem(),
                        help_text="Modules to load into the build environment."),
            yc.CategoryElem('env', sub_elem=yc.StrElem(),
                            help_text="Environment variables to set in the build environment."),
            yc.ListElem('extra_files', sub_elem=yc.StrElem(),
                        help_text='Files to copy into the build environment. Relative paths are'
                                  'searched for in ~/.pavilion, $PAV_CONFIG, and then \'./\'. '
                                  'Absolute paths are ok, but not recommended.'),
            yc.ListElem('cmds', sub_elem=yc.StrElem(),
                        help_text='The sequence of commands to run to perform the build.')
            ],
            help_text="The test build configuration. This will be used to dynamically generate a "
                      "build script for building the test."),

        yc.KeyedElem('run', elements=[
            yc.ListElem('modules', sub_elem=yc.StrElem(),
                        help_text="Modules to load into the run environment."),
            yc.CategoryElem('env', sub_elem=yc.StrElem(),
                            help_text="Environment variables to set in the run environment."),
            yc.ListElem('cmds', sub_elem=yc.StrElem(),
                        help_text='The sequence of commands to run to run the test.')
        ],
                     help_text="The test run configuration. This will be used to dynamically "
                               "generate a run script for the test."),
    ]

    @classmethod
    def add_subsection(cls, subsection):
        """Use this method to add additional sub-sections to the config.
        :param yc.ConfigElem subsection: A yaml config element to add. Keyed elements are expected,
        though any ConfigElem based instance should work.
        """

        if not isinstance(subsection, yc.ConfigElement):
            raise ValueError("Tried to add a subsection to the config, but it wasn't a yaml_config"
                             " ConfigElement instance (or an instance of a ConfigElement child "
                             "class).")

        name = subsection.name

        names = [el.name for el in cls.ELEMENTS]

        if name in names:
            raise ValueError("Tried to add a subsection to the config called {0}, but one"
                             "already exists.".format(name))

        cls.ELEMENTS.append(subsection)


class TestSuiteLoader(yc.CatYamlConfigLoader):
    """An actual test config file consists of multiple config sections."""

    _NAME_RE = KEY_NAME_RE

    # We use the list of ELEMENTS from TestConfigLoader. since this is the same object, subsections
    # added to TestConfigLoader will get picked up here too.
    BASE = yc.KeyedElem(elements=TestConfigLoader.ELEMENTS)
