"""Pavilion Test configurations, like the base Pavilion configuration,
utilize the YamlConfig library to define the config structure. Because of the
dynamic nature of test configs, there are a few extra complications this module
handles that are documented below.
"""
import collections
import copy
import re
from collections import OrderedDict
from typing import Union

import yaml_config as yc
from pavilion.errors import TestConfigError

TEST_NAME_RE_STR = r'^[a-zA-Z0-9_][a-zA-Z0-9_-]*$'
TEST_NAME_RE = re.compile(TEST_NAME_RE_STR)
KEY_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')
VAR_KEY_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
VAR_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*[?+]?$')


class PathCategoryElem(yc.CategoryElem):
    """This is for category elements that need a valid unix path regex."""
    _NAME_RE = re.compile(r".+$")


class SubVarDict(dict):
    """Subclass for variable sub-items, mainly to track defaults properly."""

    def __init__(self, *args, defaults=None, **kwargs):
        """Defaults is a dictionary of default values."""

        self.defaults = defaults or {}

        super().__init__(*args, **kwargs)

    def __copy__(self):
        """Copy over the default dict too."""

        base = {}
        for key in super().keys():
            base[key] = self[key]

        return self.__class__(base, defaults=self.defaults)

    def __deepcopy__(self, memodict=None):
        """Copy the defaults too."""

        new = SubVarDict(super().copy())
        new.defaults = copy.deepcopy(self.defaults)

        return new

    def keys(self):
        """Return all keys from both ourselves and the defaults as keys."""

        for key in set(super().keys()).union(self.defaults.keys()):
            yield key

    def items(self):
        """Return all values from both self and defaults."""

        for key in self.keys():
            yield key, self[key]

    def values(self):
        """Return all values across both self and the defaults."""

        for key in self.keys():
            yield self[key]


    def flatten(self) -> dict:
        """Return as a regular dictionary with all available values set."""

        base = {}
        for key, value in self.items():
            base[key] = value

        return base

    def is_defaults_only(self) -> bool:
        """Returns true if there isn't any regular data, just defaults."""
        return not list(super().keys())

    def super_keys(self):
        return list(super().keys())

    def __contains__(self, key):

        return key in list(super().keys()) or key in self.defaults

    def __getitem__(self, key):

        if key not in self:
            raise KeyError("KeyError: '{}'".format(key))

        if key in super().keys():
            return super().__getitem__(key)
        else:
            return self.defaults[key]

    def __str__(self):
        parts = []
        for key in self.keys():
            if key in super().keys():
                parts.append('{}: {}'.format(key, self[key]))
            else:
                parts.append('{}: ({})'.format(key, self[key]))
        return '{{ {} }}'.format(', '.join(parts))

    def __repr__(self):
        return str(self)


class VariableElem(yc.CategoryElem):
    """This is for values in the 'variables' section of a test config.

    A variable entry can be either a single string value or an
    arbitrary dictionary of strings. If given a single string value, a dictionary
    of '{None: value}' will be returned.
    """

    _NAME_RE = VAR_KEY_NAME_RE
    type = SubVarDict

    def __init__(self, name=None, **kwargs):
        """Just like a CategoryElem, but the sub_elem must be a StrElem
        and it can't have defaults."""

        super(VariableElem, self).__init__(name=name,
                                           sub_elem=yc.StrElem(),
                                           allow_empty_keys=True,
                                           **kwargs)

    def normalize(self, value, root_name='root'):
        """Normalize to either a dict of strings or just a string."""


        if not isinstance(value, dict):
            value = {None: value}

        return super().normalize(value)

    def validate(self, value, partial=False):
        """Check for a single item and return it, otherwise return a dict."""

        if not isinstance(value, dict):
            value = {None: value}

        return super().validate(value, partial=partial)


class CondCategoryElem(yc.CategoryElem):
    """Allow any key. They'll be validated later."""
    _NAME_RE = re.compile(r'^.*$')


class EvalCategoryElem(yc.CategoryElem):
    """Allow keys that start with underscore. Lowercase only."""

    _NAME_RE = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')


class VarKeyCategoryElem(yc.CategoryElem):
    """Allow Pavilion variable name like keys."""

    # Allow names that have multiple, dot separated components, potentially
    # including a '*'.
    _NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*'
                          r'(?:\.|[a-zA-Z][a-zA-Z0-9_-]*)*')


class ResultParserCatElem(yc.CategoryElem):
    """Result parser category element."""
    _NAME_RE = re.compile(
        r'^[a-zA-Z_]\w*(\s*,\s*[a-zA-Z_]\w*)*$'
    )


class VarCatElem(yc.CategoryElem):
    """For describing how the variables' section itself works.

    Just like a regular category elem (any conforming key, but values must
    be the same type), but with some special magic when merging values.

    :cvar _NAME_RE: Unlike normal categoryElem keys, these can have dashes.
    """
    _NAME_RE = VAR_NAME_RE

    def validate(self, value, partial=False):
        """Make sure default value propagate through validation."""
        validated = super().validate(value, partial=partial)

        return validated

    def merge(self, old, new):
        """Merge, but allow for special keys that change our merge behavior.

        'key?: value'
          Allows values from lower levels in the config stack to override this
          one. The value is only used if no other value is given.
        'key+: value/s'
          The values are appended to the list of whatever is given by lower
          levels of the config stack.
        """

        base = copy.deepcopy(old)
        new = copy.deepcopy(new)
        for key, values in new.items():
            # Handle special key properties

            key_suffix = None
            if key[-1] in '?+':
                key_suffix = key[-1]
                key = key[:-1]

            if values is None:
                values = [SubVarDict({None: None})]

            if not isinstance(values, list):
                values = [values]

            if key_suffix is None:
                # Completely override existing values, but keep the defaults.

                existing = base.get(key, [])
                if existing:
                    # Steal the defaults from the existing items.
                    old_defaults = existing[0].defaults
                else:
                    old_defaults = {}

                base[key] = []

                # If there are no defaults, all items should have the same keys.
                if not old_defaults and values:
                    first_val_keys = set(values[0].keys())
                    for value in values[1:]:
                        if set(value.keys()) != first_val_keys:
                            if first_val_keys == {None}:
                                raise TestConfigError(
                                    "Key '{}' in the variables section has items of differing "
                                    "formats.".format(key))

                for value in values:
                    # Check that the keys being added match the defaults
                    for subkey in value:
                        if old_defaults and subkey not in old_defaults:
                            raise TestConfigError(
                                "Key '{}' in the variables section has defaults defined, but "
                                "is trying to add a new sub-key '{}'. Existing subkeys are '{}'."
                                .format(key, subkey, list(old_defaults.keys())))

                    value.defaults = old_defaults
                    base[key].append(value)

            elif key_suffix == '?':
                # If no value is set, that's ok. We'll check for these later.

                def_type = 'subvar'
                for value in values:
                    if None in value:
                        def_type = 'single_val'
                if not values:
                    def_type = 'single_val'

                if def_type == 'subvar':
                    if len(values) > 1:
                        if len(values[0]) != 1:
                            raise TestConfigError(
                                "Key '{}' in variables section is trying to set a list of "
                                "sub-var defaults, but only one is allowed.".format(key))
                    new_defaults = values[0]

                    # If we don't have any values yet, add an empty dictionary with
                    # the defaults set.
                    if key not in base:
                        base[key] = [SubVarDict(defaults=new_defaults)]
                    else:
                        # Update the defaults for all existing items.
                        for existing in base[key]:
                            if existing.defaults:
                                # When there are existing defaults, make sure not to add
                                # any new keys.
                                for def_key in new_defaults.keys():
                                    if def_key not in existing.defaults:
                                        raise TestConfigError(
                                            "Key '{}' in variables section trying to add a new "
                                            "default sub-value key '{}', but the defaults were "
                                            "already defined with keys: '{}'"
                                            .format(key, def_key, list(existing.defaults.keys()))
                                        )
                                    existing.defaults[def_key] = new_defaults[def_key]
                            else:
                                # If there aren't any existing defaults, this defines them.
                                existing.defaults = new_defaults.copy()

                elif def_type == 'single_val':
                    for value in values:
                        if None not in value:
                            raise TestConfigError(
                                "Key '{}' in the variables section has been set with defaults "
                                "of inconsistent type. A single default dict is allowed, or "
                                "one or more simple string values."
                                .format(key))

                    existing_values = base.get(key, [])
                    # Check if the existing values are just defaults.
                    for value in existing_values:
                        if not value.is_defaults_only():
                            break
                    else:
                        # If there are no existing values or the existing are just
                        # previously set defaults. Override the defaults with these new
                        # defaults.
                        new_values = []
                        for value in values:
                            # Set each item as an empty dict with a default.
                            # This allows the default list to be extended
                            new_values.append(SubVarDict(defaults=value))
                        base[key] = new_values

            elif key_suffix == '+':
                # Extend the list of items.

                if not values:
                    raise TestConfigError(
                        "Key '{}' in variables section in extend mode (has a '+' suffix) "
                        "but no values were given.".format(key))

                # Grab the defaults from an existing item, if there is one.
                existing = base.get(key, [])
                if existing:
                    existing_defaults = existing[0].defaults
                    existing_keys = list(existing[0].keys())
                else:
                    existing_defaults = {}
                    existing_keys = None

                for value in values:
                    # Check each for key conflicts
                    for subkey in value.keys():
                        if existing_keys and subkey not in existing_keys:
                            raise TestConfigError(
                                "Key '{}' in variables section trying to add a new subkey '{}', "
                                "but the subkeys have already been set as: {}"
                                .format(key, subkey, list(existing_defaults.keys())))

                    # Add each value.
                    value.defaults = existing_defaults
                    existing.append(value)

                base[key] = existing

            else:
                # Should never happen
                raise RuntimeError("Invalid Variable Key Suffix '{}' for key '{}'"
                                   .format(key_suffix, key))

        return base

    def _check_val_merge(self, old: dict, new: dict) -> Union[None, str]:
        """Check that every key in 'new' exists in 'old'. Returns the first
         string found that doesn't match or None if everything is fine."""

        _ = self

        for key in new:
            if key not in old:
                return key

        return None


class EnvCatElem(yc.CategoryElem):
    """A category element that ensures environment variables retain their
    order."""

    _NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
    type = OrderedDict


class TestCatElem(yc.CategoryElem):
    """A category element that ensures order of Keyed Elems retain order."""

    _NAME_RE = re.compile(r'^.*$')
    type = OrderedDict


class ModuleWrapperCatElem(yc.CategoryElem):
    """Allow glob wildcards in key names."""

    _NAME_RE = re.compile(r'^[a-zA-Z*?+][a-zA-Z0-9_*+?-]*$')
    type=OrderedDict


NO_WORKING_DIR = '<no_working_dir>'


class TestConfigLoader(yc.YamlConfigLoader):
    """This class describes a test section in a Pavilion config file. It is
expected to be added to by various plugins.
"""
    SCHEDULE_CLASS = None

    ELEMENTS = [
        yc.StrElem(
            'name', hidden=True, default='<unnamed>',
            help_text="The base name of the test. Value added automatically."),
        yc.StrElem(
            'cfg_label', hidden=True, default='_none',
            help_text="The configuration label for where this test was defined."),
        yc.StrElem(
            'suite', hidden=True, default='<no_suite>',
            help_text="The name of the suite. Value added automatically."),
        yc.StrElem(
            'suite_path', hidden=True, default='<no_suite>',
            help_text="Path to the suite file. Value added automatically."),
        yc.StrElem(
            'working_dir', hidden=True, default=NO_WORKING_DIR,
            help_text="The working directory where this test will be built and "
                      "run. Added automatically."),
        yc.StrElem(
            'os', hidden=True, default='<unknown>',
            help_text="Operating system used in the creation of this test. "
                      "Value is added automatically."
        ),
        yc.StrElem(
            'host', hidden=True, default='<unknown>',
            help_text="Host (typically sys.sys_name) for which this test was "
                      "created. Value added automatically."
        ),
        yc.ListElem(
            'modes', hidden=True, sub_elem=yc.StrElem(),
            help_text="Modes used in the creation of this test. Value is added "
                      "automatically."
        ),
        yc.ListElem(
            'overrides', hidden=True, sub_elem=yc.StrElem(),
            help_text="Overrides used when creating this test. Value is added "
                      "automatically."
        ),
        yc.RegexElem(
            'inherits_from', regex=TEST_NAME_RE_STR,
            help_text="Inherit from the given test section, and override "
                      "parameters those specified in this one. Lists are "
                      "overridden entirely"),
        yc.StrElem(
            'subtitle',
            help_text="An extended title for this test. Required for "
                      "permuted tests."),
        yc.StrElem(
            'group', default=None,
            help_text="No longer used."),
        yc.StrElem(
            'umask', default=None,
            help_text="No longer used."),
        yc.KeyedElem(
            'maintainer',
            help_text="Information about who maintains this test.",
            elements=[
                yc.StrElem('name', default='unknown',
                           help_text="Name or organization of the maintainer."),
                yc.StrElem('email',
                           help_text="Email address of the test maintainer."),
            ]
        ),
        yc.StrElem(
            'summary',
            help_text="Summary of the purpose of this test."
        ),
        yc.StrElem(
            'doc',
            help_text="Detailed documentation string for this test."
        ),
        yc.ListElem(
            'permute_on', sub_elem=yc.StrElem(),
            help_text="List of permuted variables. For every permutation of "
                      "the values of these variables, a new virtual test will "
                      "be generated."
        ),
        yc.StrElem(
            'permute_base', hidden=True,
            help_text="Set by pavilion. An id to identify the base config shared by "
                      "a set of permutations."),
        yc.StrElem(
            'shebang', default='#!/usr/bin/bash',
            help_text="The shebang to put at the top of build/run/kickoff scripts. "
                      "Should always pint to 'bash', but the path and options may vary "
                      "per-system."),
        VarCatElem(
            'variables', sub_elem=yc.ListElem(sub_elem=VariableElem()),
            help_text="Variables for this test section. These can be "
                      "inserted strings anywhere else in the config through "
                      "the string syntax. They keys 'var', 'per', 'pav', "
                      "'sys' and 'sched' reserved. Each value may be a "
                      "single or list of strings key/string pairs."),
        yc.RegexElem('scheduler', regex=r'\w+', default="raw",
                     help_text="The scheduler class to use to run this test."),
        yc.StrElem(
            'sched_data_id', hidden=True,
            help_text="Used to track the scheduler data gathered for a particular "
                      "group of tests. Not to be set by the user."),
        yc.StrElem(
            'chunk', default='any',
            help_text="The scheduler chunk to run on. Will run on 'any' chunk "
                      "by default, but the chunk may be specified by number. The "
                      "available chunk ids are in the sched.chunks variable, and "
                      "can be permuted on."
        ),
        CondCategoryElem(
            'only_if', sub_elem=yc.ListElem(sub_elem=yc.StrElem()),
            key_case=EnvCatElem.KC_MIXED,
            help_text="Only run this test if each of the clauses in this "
                      "section evaluate to true. Each clause consists of "
                      "a mapping key (that can contain Pavilion variable "
                      "references, like '{{pav.user}}' or '{{sys.sys_arch}}'"
                      ") and one or more regex values "
                      "(that much match the whole key). A clause is true "
                      "if the value of the Pavilion variable matches one or "
                      "more of the values. "
        ),
        CondCategoryElem(
            'not_if', sub_elem=yc.ListElem(sub_elem=yc.StrElem()),
            key_case=EnvCatElem.KC_MIXED,
            help_text="Will NOT run this test if at least one of the "
                      "clauses evaluates to true. Each clause consists of "
                      "a mapping key (that can contain Pavilion variable "
                      "references, like '{{pav.user}}' or "
                      "'{{sys.sys_arch}}') and one or more "
                      "regex values (that much match the whole key). "
                      "A clause is true if the value of "
                      "the Pavilion variable matches one or more of the "
                      " values."
        ),
        yc.StrElem(
            'compatible_pav_versions', default='',
            help_text="Specify compatible pavilion versions for this "
                      "specific test. Can be represented as a single "
                      "version, ex: 1, 1.2, 1.2.3, or a range, "
                      "ex: 1.2-1.3.4, etc."
        ),
        yc.StrElem(
            'test_version', default='0.0',
            help_text="Documented test version."
        ),
        yc.KeyedElem(
            'spack', elements=[
                yc.StrElem(
                    'build_jobs', default='4',
                    help_text='The maximum number of jobs to use '
                              'when running \'make\' in parallel.'
                ),
                yc.CategoryElem(
                    'mirrors', sub_elem=yc.StrElem(),
                    help_text='The keys and values of this section '
                              'wil be added as mirrors to the spack '
                              'environment for this build.'
                ),
                yc.ListElem(
                    'repos', sub_elem=yc.StrElem(),
                    help_text='This is a list of repos spack will '
                              'search through for packages before '
                              'attempting to build.'
                ),
                yc.CategoryElem(
                    'upstreams', sub_elem=yc.KeyedElem(
                        elements=[
                            yc.StrElem('install_tree')
                        ]),
                    help_text="Upstream spack installs."
                ),
            ],
            help_text="Spack configuration items to set in this test's "
                      "spack.yaml file."
        ),
        yc.KeyedElem(
            'build', elements=[
                yc.ListElem(
                    'cmds', sub_elem=yc.StrElem(),
                    help_text='The sequence of commands to run to perform '
                              'the build.'),
                yc.ListElem(
                    'prepend_cmds', sub_elem=yc.StrElem(),
                    help_text='Commands to run before inherited build '
                              'commands.'),
                yc.ListElem(
                    'append_cmds', sub_elem=yc.StrElem(),
                    help_text='Commands to run after inherited build '
                              'commands.'),
                yc.ListElem(
                    'copy_files', sub_elem=yc.StrElem(),
                    help_text="When attaching the build to a test run, copy "
                              "these files instead of creating a symlink. "
                              "They may include path glob wildcards, "
                              "including the recursive '**'."),
                PathCategoryElem(
                    'create_files',
                    key_case=PathCategoryElem.KC_MIXED,
                    sub_elem=yc.ListElem(sub_elem=yc.StrElem()),
                    help_text="File(s) to create at path relative to the test's "
                              "build/run directory. The key is the filename, "
                              "while the contents is a list of lines to include in the "
                              "file. Pavilion test variables will be resolved in this lines "
                              "before they are written."),
                PathCategoryElem(
                    'templates',
                    key_case=PathCategoryElem.KC_MIXED,
                    sub_elem=yc.StrElem(),
                    help_text="Template files to resolve using Pavilion test variables. The "
                              "key is the path to the template file (typically with a "
                              "'.pav' extension), in the 'test_src' directory. The value is the "
                              "output file location, relative to the test's build/run "
                              "directory."),
                EnvCatElem(
                    'env', sub_elem=yc.StrElem(), key_case=EnvCatElem.KC_MIXED,
                    help_text="Environment variables to set in the build "
                              "environment."),
                yc.ListElem(
                    'extra_files', sub_elem=yc.StrElem(),
                    help_text='File(s) to copy into the build environment. '
                              'Relative paths searched for in ~/.pavilion, '
                              '$PAV_CONFIG. Absolute paths are ok, '
                              'but not recommended.'),
                yc.ListElem(
                    'modules', sub_elem=yc.StrElem(),
                    help_text="Modules to load into the build environment."),
                yc.StrElem(
                    'on_nodes', default='False',
                    choices=['true', 'false', 'True', 'False'],
                    help_text="Whether to build on or off of the test "
                              "allocation."),
                yc.ListElem(
                    'preamble', sub_elem=yc.StrElem(),
                    help_text="Setup commands for the beginning of the build "
                              "script. Added to the beginning of the run "
                              "script.  These are generally expected to "
                              "be host rather than test specific."),
                yc.StrElem(
                    'source_path',
                    help_text="Path to the test source. It may be a directory, "
                              "compressed file, compressed or "
                              "uncompressed archive (zip/tar), and is handled "
                              "according to the internal (file-magic) type. "
                              "For relative paths Pavilion looks in the "
                              "test_src directory "
                              "within all known config directories. If this "
                              "is left blank, Pavilion will always assume "
                              "there is no source to build."),
                yc.StrElem(
                    'source_url',
                    help_text='Where to find the source on the internet. By '
                              'default, Pavilion will try to download the '
                              'source from the given URL if the source file '
                              'can\'t otherwise be found. You must give a '
                              'source path so Pavilion knows where to store '
                              'the file (relative paths will be stored '
                              'relative to the local test_src directory.'),
                yc.StrElem(
                    'source_download', choices=['never', 'missing', 'latest'],
                    default='missing',
                    help_text="When to attempt to download the test source.\n"
                              "  never - The url is for reference only.\n"
                              "  missing - (default) Download if the source "
                              "can't be found.\n"
                              "  latest - Always try to fetch the latest "
                              "source, tracking changes by "
                              "file size/timestamp/hash."
                ),
                yc.KeyedElem(
                    'spack', elements=[
                        yc.ListElem(
                            'install', sub_elem=yc.StrElem(),
                            help_text='The list of spack packages to be '
                                      'installed.'
                        ),
                        yc.ListElem(
                            'load', sub_elem=yc.StrElem(),
                            help_text='The list of spack packages to be '
                                      'loaded.'
                        ),
                    ],
                    help_text='Spack package build configs.'),
                yc.StrElem(
                    'specificity',
                    default='',
                    help_text="Use this string, along with variables, to "
                              "differentiate builds. A common example would be "
                              "to make per-host specific by using the "
                              "sys.sys_name variable. Note _deferred_ system "
                              "variables aren't a good idea hereas configs are "
                              "compiled on the host that launches the test."),
                yc.StrElem(
                    'timeout',
                    default='30',
                    help_text="Time (in seconds) that a build can continue "
                              "without generating new output before it is "
                              "cancelled.  Can be left empty for no timeout."),
                yc.StrElem(
                    'verbose', choices=['true', 'True', 'False', 'false'],
                    default='False',
                    help_text="Echo commands (including sourced files) in the"
                              " build log, and print the modules loaded and "
                              "environment before the cmds run."),
                yc.StrElem(
                    'timeout_file', default=None,
                    help_text='Specify a different file to follow for build '
                              'timeouts.'),
                yc.StrElem(
                    'autoexit',  choices=['true', 'True', 'False', 'false'],
                    default='True',
                    help_text='If True, test will fail if any of its build '
                              'commands fail, rather than just the last '
                              'command.'),
            ],
            help_text="The test build configuration. This will be "
                      "used to dynamically generate a build script for "
                      "building the test."),

        yc.KeyedElem(
            'run', elements=[
                yc.ListElem('cmds', sub_elem=yc.StrElem(),
                            help_text='The sequence of commands to run to run '
                                      'the test.'),
                yc.ListElem(
                    'prepend_cmds', sub_elem=yc.StrElem(),
                    help_text='Commands to run before inherited run commands.'),
                yc.ListElem(
                    'append_cmds', sub_elem=yc.StrElem(),
                    help_text='Commands to run after inherited run commands.'),
                PathCategoryElem(
                    'create_files',
                    key_case=PathCategoryElem.KC_MIXED,
                    sub_elem=yc.ListElem(sub_elem=yc.StrElem()),
                    help_text="File(s) to create at path relative to the test's "
                              "build/run directory. The key is the filename, "
                              "while the contents is a list of lines to include in the "
                              "file. Pavilion test variables will be resolved in this lines "
                              "before they are written."),

                # Note - Template have to come from the test_src directory (or elsewhere on
                #        the filesystem, because we have to be able to process them before
                #        we can create a build hash.
                PathCategoryElem(
                    'templates',
                    key_case=PathCategoryElem.KC_MIXED,
                    sub_elem=yc.StrElem(),
                    help_text="Template files to resolve using Pavilion test variables. The "
                              "key is the path to the template file (typically with a "
                              "'.pav' extension), in the 'test_src' directory. The value is the "
                              "output file location, relative to the test's build/run "
                              "directory."),
                EnvCatElem(
                    'env', sub_elem=yc.StrElem(), key_case=EnvCatElem.KC_MIXED,
                    help_text="Environment variables to set in the run "
                              "environment."),
                yc.ListElem(
                    'modules', sub_elem=yc.StrElem(),
                    help_text="Modules to load into the run environment."),
                yc.ListElem(
                    'preamble', sub_elem=yc.StrElem(),
                    help_text="Setup commands for the beginning of the build "
                              "script. Added to the beginning of the run "
                              "script. These are generally expected to "
                              "be host rather than test specific."),
                yc.KeyedElem(
                    'spack', elements=[
                        yc.ListElem(
                            'load', sub_elem=yc.StrElem(),
                            help_text='The list of spack packages to be '
                                      'loaded.'
                        )
                    ],
                    help_text='Used to specify spack package loads and '
                              'installs.'),
                yc.StrElem(
                    'timeout', default='300',
                    help_text="Time that a build can continue without "
                              "generating new output before it is cancelled. "
                              "Can be left empty for no timeout."),
                yc.StrElem(
                    'verbose', choices=['true', 'True', 'False', 'false'],
                    default='False',
                    help_text="Echo commands (including sourced files) in the "
                              "build log, and print the modules loaded and "
                              "environment before the cmds run."),
                yc.StrElem(
                    'timeout_file', default=None,
                    help_text='Specify a different file to follow for run '
                              'timeouts.'),
                yc.StrElem(
                    'autoexit', choices=['true', 'True', 'False', 'false'],
                    default='True',
                    help_text='If True, test will fail if any of its run commands '
                              'fail, rather than just the last command.'),
            ],
            help_text="The test run configuration. This will be used "
                      "to dynamically generate a run script for the "
                      "test."),
        EvalCategoryElem(
            'result_evaluate',
            sub_elem=yc.StrElem(),
            help_text="The keys and values in this section will also "
                      "be added to the result json. The values are "
                      "expressions (like in {{<expr>}} in normal Pavilion "
                      "strings). Other result values (including those "
                      "from result parsers and other evaluations are "
                      "available to reference as variables."),
        ModuleWrapperCatElem(
            'module_wrappers',
            help_text="Whenever the given module[/version] is asked for in the 'build.modules' "
                      "or 'run.modules' section, perform these module actions instead and "
                      "export the given environment variables. When this module is requested via "
                      "a 'swap', do the swap as written but set the given environment variables. "
                      "Nothing special is done for module unloads of this module. "
                      "If a version is given, this only applies to that specific version.",
            sub_elem=yc.KeyedElem(
                elements=[
                    yc.ListElem(
                        'modules', sub_elem=yc.StrElem(),
                        help_text="Modules to load/remove/swap when the given module "
                                  "is specified. Loads and swaps into the wrapped module "
                                  "will automatically be at the requested version if none "
                                  "is given.  (IE - If the user asks for gcc/5.2, a "
                                  "listing of just 'gcc' here will load 'gcc/5.2')."),
                    EnvCatElem(
                        'env', sub_elem=yc.StrElem(),
                        help_text="Environment variables to set after performing the "
                                  "given module actions. A '<MODNAME_VERSION>' variable "
                                  "will also be set with the specified version, if given.")
                ]
            )
        ),
    ]
    """Each YamlConfig instance in this list defines a key for the test config.

        - Each element must result in a string (which is why you see a lot of
          StrElem below), or a structure that contains only strings at the
          lowest layer.

          - So lists of dicts of strings are fine, etc.
          - yc.RegexElem also produces a string.
        - Everything should have a sensible default.

          - An empty config should be a valid test.
        - For bool values, accept ['true', 'false', 'True', 'False'].

          - They should be checked with val.lower() == 'true', etc.
        - Every element must have a useful 'help_text'.
    """

    # We'll append the result parsers separately, to have an easy way to
    # access it.
    _RESULT_PARSERS = yc.KeyedElem(
        'result_parse', elements=[],
        help_text="Result parser configurations go here. Each parser config "
                  "can occur by itself or as a list of configs, in which "
                  "case the parser will run once for each config given. The "
                  "output of these parsers will be added to the final "
                  "result json data.")
    ELEMENTS.append(_RESULT_PARSERS)

    def __init__(self):
        """Add the schedule config class and then init as normal."""

        if self.SCHEDULE_CLASS is None:
            raise RuntimeError("The config's scheduler config class should have been "
                               "set by Pavilion's __init__.py file.")

        for element in self.ELEMENTS:
            if element.name == 'schedule':
                break
        else:
            self.ELEMENTS.append(self.SCHEDULE_CLASS())

        super().__init__(name='<test_config>')

    @classmethod
    def add_result_parser_config(cls, name, config_items):
        """Add the given list of config items as a result parser
        configuration named 'name'. Throws errors for invalid configurations.
        """

        # Validate the config.
        required_keys = {
            'files': False,
            'action': False,
            'per_file': False,
        }
        for item in config_items:
            for req_key in required_keys.keys():
                if item.name == req_key:
                    required_keys[req_key] = True

        for req_key, found in required_keys.items():
            if not found:
                raise TestConfigError(
                    "Result parser '{}' must have a required config "
                    "element named '{}'".format(name, req_key))

        config = yc.KeyedElem(
            'result_parser_{}'.format(name),
            elements=config_items
        )

        list_elem = ResultParserCatElem(name, sub_elem=config)

        if name in [e.name for e in cls._RESULT_PARSERS.config_elems.values()]:
            raise ValueError("Tried to add result parser with name '{}' "
                             "to the config, but one already exists."
                             .format(name))

        try:
            cls.check_leaves(config)
        except ValueError as err:
            raise ValueError("Tried to add result parser named '{}', but "
                             "leaf element '{}' was not string based."
                             .format(name, err.args[0]))

        cls._RESULT_PARSERS.config_elems[name] = list_elem

    @classmethod
    def remove_result_parser_config(cls, name):
        """Remove the given result parser from the result parser configuration
        section.

        :param str name: The name of the parser to remove.
        """

        for section in list(cls._RESULT_PARSERS.config_elems.values()):
            if section.name == name:
                del cls._RESULT_PARSERS.config_elems[section.name]
                return

    @classmethod
    def check_leaves(cls, elem):
        """Make sure all of the config elements have a string element or
        equivalent as the final node.

        :param yc.ConfigElement elem:
        """

        # pylint: disable=protected-access

        if hasattr(elem, 'config_elems'):
            for sub_elem in elem.config_elems.values():
                cls.check_leaves(sub_elem)
        elif hasattr(elem, '_sub_elem') and elem._sub_elem is not None:
            cls.check_leaves(elem._sub_elem)
        elif issubclass(elem.type, str):
            return
        else:
            raise ValueError(elem)


def TestSuiteLoader():  # pylint: disable=invalid-name
    """Create a new test suite loader instance. This is a function
    masquerading as a constructor because the class has to be defined
    dynamically after plugins have modified the test config.
    """

    class _TestSuiteLoader(yc.CatYamlConfigLoader):
        """An actual test config file consists of multiple config sections."""

        _NAME_RE = TEST_NAME_RE

        # We use the list of ELEMENTS from TestConfigLoader. since this is the
        # same object, subsections added to TestConfigLoader will get picked up
        # here too.
        BASE = TestConfigLoader()

    return _TestSuiteLoader()
