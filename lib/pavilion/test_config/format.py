import yaml_config as yc
import re


class TestConfigError(ValueError):
    """An exception specific to errors in configuration."""
    pass


KEY_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')


class VariableElem(yc.CategoryElem):
    """A variable entry can be either a single string value or a dictionary
    of values. If we get a single value, we'll return it instead of a dict."""

    _NAME_RE = KEY_NAME_RE

    def __init__(self, name=None, **kwargs):
        """Just like a CategoryElem, but we force some of the params."""
        super(VariableElem, self).__init__(name=name,
                                           sub_elem=yc.StrElem(),
                                           defaults=None,
                                           **kwargs)

    def normalize(self, values):
        if isinstance(values, str):
            return values

        return super().normalize(values)

    def validate(self, value_dict, partial=False):
        """Check for a single item and return it, otherwise return a dict."""

        if isinstance(value_dict, str):
            return value_dict

        return super().validate(value_dict, partial=partial)


class VarCatElem(yc.CategoryElem):
    """Just like a regular category elem, but we override the key regex to
    allow dashes. We won't be using name style references anyway."""
    _NAME_RE = KEY_NAME_RE


class TestConfigLoader(yc.YamlConfigLoader):
    """This class describes a test section in a Pavilion config file. It is
    expected to be added to by various plugins."""

    ELEMENTS = [
        yc.RegexElem(
            'inherits_from', regex=r'\w+',
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
        VarCatElem(
            'variables', sub_elem=yc.ListElem(sub_elem=VariableElem()),
            help_text="Variables for this test section. These can be "
                      "inserted strings anywhere else in the config through "
                      "the string syntax. They keys 'var', 'per', 'pav', "
                      "'sys' and 'sched' reserved. Each value may be a "
                      "single or list of strings key/string pairs."),
        VarCatElem(
            'permutations', sub_elem=yc.ListElem(sub_elem=VariableElem()),
            help_text="Permutation variables for this test section. These are "
                      "just like normal variables, but they if a list of "
                      "values (whether a single string or key/string pairs) "
                      "is given, then a virtual test is created for each "
                      "combination across all variables in each section. The "
                      "resulting virtual test is thus given a single "
                      "permutation of these values."),
        yc.RegexElem('scheduler', regex=r'\w+', default="raw",
                     help_text="The scheduler class to use to run this test."),
        yc.KeyedElem('build', elements=[
            yc.StrElem(
                'on_nodes', default='False',
                choices=['true', 'false', 'True', 'False'],
                help_text="Whether to build on or off of the test allocation."
            ),
            yc.StrElem(
                'source_location',
                help_text="Path to the test source. It may be a directory, "
                          "a tar file, or a URI. If it's a directory or "
                          "file, the path is to '$PAV_CONFIG/test_src' by "
                          "default. For url's, the is automatically checked "
                          "for updates every time the test run. Downloaded "
                          "files are placed in a 'downloads' under the "
                          "pavilion working directory. (set in pavilion.yaml)"),
            yc.StrElem(
                'source_download_name',
                help_text='When downloading source, we by default use the '
                          'last of the url path as the filename, or a hash '
                          'of the url if is no suitable name. Use this '
                          'parameter to override behavior with a pre-defined '
                          'filename.'),
            yc.ListElem(
                'modules', sub_elem=yc.StrElem(),
                help_text="Modules to load into the build environment."),
            yc.CategoryElem(
                'env', sub_elem=yc.StrElem(),
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
            yc.ListElem('cmds', sub_elem=yc.StrElem(),
                        help_text='The sequence of commands to run to perform '
                                  'the build.')
            ],
            help_text="The test build configuration. This will be used to "
                      "dynamically generate a build script for building "
                      "the test."),

        yc.KeyedElem('run', elements=[
            yc.ListElem('modules', sub_elem=yc.StrElem(),
                        help_text="Modules to load into the run environment."),
            yc.CategoryElem('env', sub_elem=yc.StrElem(),
                            help_text="Environment variables to set in the run "
                                      "environment."),
            yc.ListElem('cmds', sub_elem=yc.StrElem(),
                        help_text='The sequence of commands to run to run the '
                                  'test.')
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
        found_key = False
        found_file = False
        for item in config_items:
            if item.name == 'key' and item.required:
                found_key = True
            elif item.name == 'file':
                found_file = True

        if not found_key:
            raise TestConfigError(
                "Result parser '{}' must have a required config "
                "element named 'key'".format(name))
        if not found_file:
            raise TestConfigError(
                "Result parser '{}' must have a config element named 'file'."
                .format(name))

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
        :return:
        """

        for section in list(cls._RESULT_PARSERS.config_elems.values()):
            if section.name == name:
                del cls._RESULT_PARSERS.config_elems[section.name]
                return

    @classmethod
    def check_leaves(cls, elem):
        """
        :param yc.ConfigElement elem:
        :return:
        """

        if hasattr(elem, 'config_elems'):
            for sub_elem in elem.config_elems.values():
                cls.check_leaves(sub_elem)
        elif hasattr(elem, '_sub_elem') and elem._sub_elem is not None:
            cls.check_leaves(elem._sub_elem)
        elif issubclass(elem.type, str):
            return
        else:
            raise ValueError(elem)


# TODO: Fix this name.
def TestSuiteLoader():
    """Create a new test suite loader instance. This has to be done
    dynamically because of how we add keys to the TestConfig above."""

    class _TestSuiteLoader(yc.CatYamlConfigLoader):
        """An actual test config file consists of multiple config sections."""

        _NAME_RE = KEY_NAME_RE

        # We use the list of ELEMENTS from TestConfigLoader. since this is the
        # same object, subsections added to TestConfigLoader will get picked up
        # here too.
        BASE = yc.KeyedElem(elements=TestConfigLoader.ELEMENTS)

    return _TestSuiteLoader()
