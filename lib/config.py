#  ###################################################################
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

import dependencies.yaml_config as yc


class VariableElem(yc.CategoryElem):
    """A variable entry can be either a single value or a dictionary of values. If we get
    a single value, we'll set it to the 'None' key of the resulting dict."""

    def __init__(self, name=None, **kwargs):
        """Just like a CategoryElem, but we force some of the params."""
        super(VariableElem, self).__init__(name=name,
                                           sub_elem=yc.StrElem(),
                                           defaults=None,
                                           **kwargs)

    def validate(self, value_dict):
        """Check for a single item, and force it into a dict."""

        if issubclass(basestring, value_dict):
            value_dict = {None: value_dict}

        return super(VariableElem, self).validate(value_dict)


class TestSection(yc.YamlConfigLoader):
    """This class describes a test section in a Pavilion config file. It is expected to be
    added to by various plugins."""

    ELEMENTS = [
        yc.StrElem('inherits_from',
                   help_text="Inherit from the given test section, and override parameters with"
                             "those specified in this one. Lists are overridden entirely"),
        yc.StrElem('scheduler',
                   help_text="The scheduler class to use to run this test."),
        yc.StrElem('source_location',
                   help_text="Path to the test source. It may be a directory, a tar file, "
                             "or a git URI. If it's a directory or file, the path is relative to "
                             "'$PAV_CONFIG/test_src' by default."),
        yc.CategoryElem('vars', sub_elem=yc.ListElem(sub_elem=VariableElem),
                        help_text="Variables for this test section. These can be inserted into "
                                  "strings anywhere else in the config through python .format "
                                  "syntax. The keys 'build', 'run', 'pav', and 'sched' are "
                                  "reserved. If more than one value is given for a variable, "
                                  "a virtual test section will be created for every combination "
                                  "of such multi-valued variables. If a dictionary is given as a "
                                  "value (either alone, or as part of a list), then that will "
                                  "create a variable with multiple sub values (and no value "
                                  "itself) The subvalues may be accessed as if they were "
                                  "properties (ie var.sub_var)."),
        yc.KeyedElem('build', elements=[
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


class TestConfig(yc.CatYamlConfigLoader):
    """An actual test config file consists of multiple config sections."""

    # We use the list of ELEMENTS from TestSection. since this is the same object, subsections
    # added to TestSection will get picked up here too.
    BASE = yc.KeyedElem(elements=TestSection.ELEMENTS)
