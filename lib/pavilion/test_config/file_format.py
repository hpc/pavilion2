"""Pavilion Test configurations, like the base Pavilion configuration,
utilize the YamlConfig library to define the config structure. Because of the
dynamic nature of test configs, there are a few extra complications this module
handles that are documented below.
"""

from collections import OrderedDict
import re
import yaml_config as yc


class TestConfigError(ValueError):
    """An exception specific to errors in configuration."""


TEST_NAME_RE_STR = r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
TEST_NAME_RE = re.compile(TEST_NAME_RE_STR)
KEY_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')
VAR_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*[\?\+]?$')


class VariableElem(yc.CategoryElem):
    """This is for values in the 'variables' section of a test config.

    A variable entry can be either a single string value or an
    arbitrary dictionary of strings. If we get a single value, we'll return it
    instead of a dict.  Pavilion's variable handling code handles the
    normalization of these values.
    """

    _NAME_RE = KEY_NAME_RE

    def __init__(self, name=None, **kwargs):
        """Just like a CategoryElem, but the sub_elem must be a StrElem
        and it can't have defaults."""
        super(VariableElem, self).__init__(name=name,
                                           sub_elem=yc.StrElem(),
                                           defaults=None,
                                           **kwargs)

    def normalize(self, values):
        """Normalize to either a dict of strings or just a string."""
        if isinstance(values, str):
            return values

        return super().normalize(values)

    def validate(self, value_dict, partial=False):
        """Check for a single item and return it, otherwise return a dict."""

        if isinstance(value_dict, str):
            return value_dict

        return super().validate(value_dict, partial=partial)


class VarCatElem(yc.CategoryElem):
    """For describing how the variables section itself works.

    Just like a regular category elem (any conforming key, but values must
    be the same type), but with some special magic when merging values.

    :cvar _NAME_RE: Unlike normal categoryElem keys, these can have dashes.
    """
    _NAME_RE = VAR_NAME_RE

    def merge(self, old, new):
        """Merge, but allow for special keys that change our merge behavior.

        'key?: value'
          Allows values from lower levels in the config stack to override this
          one. The value is only used if no other value is given.
        'key+: value/s'
          The values are appended to the list of whatever is given by lower
          levels of the config stack.
        """

        base = old.copy()
        for key, value in new.items():
            # Handle special key properties
            if key[-1] in '?+':
                bkey = key[:-1]
                new_vals = new[key]

                if key.endswith('?'):
                    if new_vals is None:
                        raise TestConfigError(
                            "Key '{key}' in variables section must have a "
                            "value, either set as the default at this level or "
                            "provided by an underlying host or mode config."
                            .format(key=key)
                        )
                    # Use the new value only if there isn't an old one.
                    base[bkey] = base.get(bkey, new[key])
                elif key.endswith('+'):
                    if new_vals is None:
                        raise TestConfigError(
                            "Key '{key}' in variables section is in extend "
                            "mode, but provided no values."
                            .format(key=key))

                    # Appending the additional (unique) values
                    base[bkey] = base.get(bkey, self._sub_elem.type())
                    for item in new_vals:
                        if item not in base[bkey]:
                            base[bkey].append(item)

            elif key in old:
                base[key] = self._sub_elem.merge(old[key], new[key])
            else:
                base[key] = new[key]

        return base


class EnvCatElem(yc.CategoryElem):
    """A category element that ensures environment variables retain their
    order."""

    _NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
    type = OrderedDict


class TestConfigLoader(yc.YamlConfigLoader):
    """This class describes a test section in a Pavilion config file. It is
expected to be added to by various plugins.

:cvar list(yc.YamlConfig) ELEMENTS: Each YamlConfig instance in this
    list defines a key for the test config.

- Each element must result in a string (which is why you see a lot of StrElem
  below), or a structure that contains only strings at the lowest layer.

  - So lists of dicts of strings are fine, etc.
  - yc.RegexElem also produces a string.
- Everything should have a sensible default.

  - An empty config should be a valid test.
- For bool values, accept ['true', 'false', 'True', 'False'].

  - They should be checked with val.lower() == 'true', etc.
- Every element must have a useful 'help_text'.
"""

    ELEMENTS = [
        yc.RegexElem(
            'inherits_from', regex=TEST_NAME_RE_STR,
            help_text="Inherit from the given test section, and override "
                      "parameters those specified in this one. Lists are "
                      "overridden entirely"),
        yc.StrElem(
            'subtitle',
            help_text="An extended title for this test. This is useful for "
                      "assigning unique name to virtual tests through "
                      "variable insertion. example, if a test has a single "
                      "permutation variable 'subtest', then '{subtest}' "
                      "would give a useful descriptor."),
        yc.StrElem(
            'summary', default='',
            help_text="Summary of the purpose of this test."
        ),
        yc.StrElem(
            'doc', default='',
            help_text="Detailed documentation string for this test."
        ),
        yc.ListElem(
            'permute_on', sub_elem=yc.StrElem(),
            help_text="List of permuted variables. For every permutation of "
                      "the values of these variables, a new virtual test will "
                      "be generated."
        ),
        VarCatElem(
            'variables', sub_elem=yc.ListElem(sub_elem=VariableElem()),
            help_text="Variables for this test section. These can be "
                      "inserted strings anywhere else in the config through "
                      "the string syntax. They keys 'var', 'per', 'pav', "
                      "'sys' and 'sched' reserved. Each value may be a "
                      "single or list of strings key/string pairs."),
        yc.RegexElem('scheduler', regex=r'\w+', default="raw",
                     help_text="The scheduler class to use to run this test."),
        yc.KeyedElem(
            'build', elements=[
                yc.StrElem(
                    'on_nodes', default='False',
                    choices=['true', 'false', 'True', 'False'],
                    help_text="Whether to build on or off of the test "
                              "allocation."
                ),
                yc.StrElem(
                    'source_location',
                    help_text="Path to the test source. It may be a directory, "
                              "a tar file, or a URI. If it's a directory or "
                              "file, the path is to '$PAV_CONFIG/test_src' by "
                              "default. For url's, the is automatically "
                              "checked for updates every time the test run. "
                              "Downloaded files are placed in a 'downloads' "
                              "under the pavilion working directory. (set in "
                              "pavilion.yaml)"),
                yc.StrElem(
                    'source_download_name',
                    help_text='When downloading source, we by default use the '
                              'last of the url path as the filename, or a hash '
                              'of the url if is no suitable name. Use this '
                              'parameter to override behavior with a '
                              'pre-defined filename.'),
                yc.ListElem(
                    'modules', sub_elem=yc.StrElem(),
                    help_text="Modules to load into the build environment."),
                EnvCatElem(
                    'env', sub_elem=yc.StrElem(), key_case=EnvCatElem.KC_MIXED,
                    help_text="Environment variables to set in the build "
                              "environment."),
                yc.ListElem(
                    'extra_files', sub_elem=yc.StrElem(),
                    help_text='Files to copy into the build environment. '
                              'Relative paths searched for in ~/.pavilion, '
                              '$PAV_CONFIG. Absolute paths are ok, '
                              'but not recommended.'),
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
                yc.ListElem(
                    'cmds', sub_elem=yc.StrElem(),
                    help_text='The sequence of commands to run to perform '
                              'the build.'),
                yc.ListElem(
                    'preamble', sub_elem=yc.StrElem(),
                    help_text="Setup commands for the beginning of the build "
                              "script. Added to the beginning of the run "
                              "script.  These are generally expected to "
                              "be host rather than test specific."),
                yc.StrElem(
                    'verbose', choices=['true', 'True', 'False', 'false'],
                    default='False',
                    help_text="Echo commands (including sourced files) in the"
                              " build log, and print the modules loaded and "
                              "environment before the cmds run."),
                ],
            help_text="The test build configuration. This will be "
                      "used to dynamically generate a build script for "
                      "building the test."),

        yc.KeyedElem(
            'run', elements=[
                yc.ListElem(
                    'modules', sub_elem=yc.StrElem(),
                    help_text="Modules to load into the run environment."),
                EnvCatElem(
                    'env', sub_elem=yc.StrElem(), key_case=EnvCatElem.KC_MIXED,
                    help_text="Environment variables to set in the run "
                              "environment."),
                yc.ListElem('cmds', sub_elem=yc.StrElem(),
                            help_text='The sequence of commands to run to run '
                                      'the test.'),
                yc.ListElem(
                    'preamble', sub_elem=yc.StrElem(),
                    help_text="Setup commands for the beginning of the build "
                              "script. Added to the beginning of the run "
                              "script. These are generally expected to "
                              "be host rather than test specific."),
                yc.StrElem(
                    'verbose', choices=['true', 'True', 'False', 'false'],
                    default='False',
                    help_text="Echo commands (including sourced files) in the "
                              "build log, and print the modules loaded and "
                              "environment before the cmds run."),
                yc.StrElem(
                    'timeout', default='300',
                    help_text="Time that a build can continue without "
                              "generating new output before it is cancelled. "
                              "Can be left empty for no timeout.")
            ],
            help_text="The test run configuration. This will be used "
                      "to dynamically generate a run script for the "
                      "test."),
    ]

    # We'll append the result parsers separately, to have an easy way to
    # access it.
    _RESULT_PARSERS = yc.KeyedElem(
        'results', elements=[],
        help_text="Result parser configurations go here. Each parser config "
                  "can occur by itself or as a list of configs, in which "
                  "case the parser will run once for each config given. The "
                  "output of these parsers will be combined into the final "
                  "result json data.")
    ELEMENTS.append(_RESULT_PARSERS)

    @classmethod
    def add_subsection(cls, subsection):
        """Use this method to add additional sub-sections to the config.

        :param yc.ConfigElem subsection: A yaml config element to add. Keyed
            elements are expected, though any ConfigElem based instance
            (whose leave elements are StrElems) should work.
        """

        if not isinstance(subsection, yc.ConfigElement):
            raise ValueError("Tried to add a subsection to the config, but it "
                             "wasn't a yaml_config ConfigElement instance (or "
                             "an instance of a ConfigElement child "
                             "class).")

        name = subsection.name

        names = [el.name for el in cls.ELEMENTS]

        if name in names:
            raise ValueError("Tried to add a subsection to the config called "
                             "{0}, but one already exists.".format(name))

        try:
            cls.check_leaves(subsection)
        except ValueError as err:
            raise ValueError("Tried to add result parser named '{}', but "
                             "leaf element '{}' was not string based."
                             .format(name, err.args[0]))

        cls.ELEMENTS.append(subsection)

    @classmethod
    def remove_subsection(cls, subsection_name):
        """Remove a subsection from the config. This is really only for use
        in plugin deactivate methods."""

        for section in list(cls.ELEMENTS):
            if subsection_name == section.name:
                cls.ELEMENTS.remove(section)
                return

    @classmethod
    def add_result_parser_config(cls, name, config_items):
        """Add the given list of config items as a result parser
        configuration named 'name'. Throws errors for invalid configuraitons.
        """

        # Validate the config.
        required_keys = {
            'key': False,
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

        list_elem = yc.ListElem(name, sub_elem=config)

        if name in [e.name for e in cls._RESULT_PARSERS.config_elems.values()]:
            raise ValueError("Tried to add result parser with name '{}'"
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
        BASE = yc.KeyedElem(elements=TestConfigLoader.ELEMENTS)

    return _TestSuiteLoader()
