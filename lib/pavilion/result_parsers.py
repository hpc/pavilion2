from .test_config import format
from yapsy import IPlugin
import inspect
import logging
import yaml_config as yc
from .test_config import variables


LOGGER = logging.getLogger(__file__)


# The dictionary of result parsers.
_RESULT_PARSERS = {}


def get_plugin(name):
    """Get the result plugin parser called name.
    :param str name: The name of the result parser plugin to return.
    :rtype: ResultParser

    """

    return _RESULT_PARSERS[name]


def list_plugins():
    """Return a list of result parser plugin names."""

    return list(_RESULT_PARSERS.keys())


def __reset():
    """Reset the plugin setup. This is for testing only."""

    global _RESULT_PARSERS

    # Remove all existing parsers.
    for parser in list(_RESULT_PARSERS.values()):
        parser.deactivate()


class ResultParserError(RuntimeError):
    pass


# These are the base result constants
PASS = 'PASS'
FAIL = 'FAIL'
ERROR = 'ERROR'


class ResultParser(IPlugin.IPlugin):
    """Base class for creating a result parser plugin. These are essentially
    a callable that implements operations on the test or test files. The
    arguments for the callable are provided automatically via the test
    config. The doc string of result parser classes is used as the user help
    text for that class, plus the help on the config items."""

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    def __init__(self, name, priority=PRIO_COMMON):
        """Initialize the plugin object
        :param str name: The name of this plugin.
        :param int priority: The priority of this plugin, compared to plugins
            of the same name. Higher priority plugins will supersede others.
        """

        self.name = name
        self.priority = priority

        super().__init__()

    def __call__(self, test, **kwargs):
        """This is where the result parser is actually implemented.
        :param dict kwargs: The arguments are the config values from the the
        test's result config section for this parser.
        :raises ResultParserError: When something goes wrong.
        """

        raise NotImplementedError("A result parser plugin must implement"
                                  "the __call__ method.")

    def _check_args(self, test, **kwargs):
        """Override this to add custom checking of the arguments at test
        kickoff time. This prevents errors in your arguments from causing
        a problem in the middle of a test run. The yaml_config module handles
        structural checking (and can handle more). This should raise a
        descriptive ResultParserError if any issues are found.
        :param pavilion.test_config.PavTest test: The test object that this
            result parser will be working with.
        :param kwargs: Child result parsers should override these with
            specific kwargs for their arguments. They should all default to
            and rely on the config parser to set their defaults.
        """

        pass

    def check_args(self, test, args):
        """Check the arguments for any errors at test kickoff time, if they
        don't contain deferred variables. We can't check tests with
        deferred args. On error, should raise a ResultParserError.
        :param pavilion.pav_test.PavTest test: The test to check against.
        :param dict args: The arguments from the config.
        """

        if variables.VariableSetManager.has_deferred(args):
            return

        self._check_args(test, **args)

    KEY_REGEX_STR = r'^[a-z0-9_-]+$'

    def get_config_items(self):
        """Get the config for this result parser. This should be a list of
        yaml_config.ConfigElement instances that will be added to the test
        config format at plugin activation time. The simplest format is a
        list of yaml_config.StrElem objects, but any structure is allowed
        as long as the leaf elements are StrElem type.

        Every result parser is expected to take the following arguments:
            'file' - The path to the file to examine (relative to the test
                     build directory), defaults to the test run's log.
                     Some parsers may ignore (or change the meaning of)
                     this argument.
            'key' - The name to give the result in the result json. (No
                    default)

        Example:
            config_items = super().get_config_items()
            config_items.append(
                yaml_config.StrElem('token', default='PASSED',
                    help="The token to search for in the file."
            )
            return config_items
        """

        return [
            yc.RegexElem("key", required=True,
                         regex=self.KEY_REGEX_STR,
                         help_text="The key value in the result json for this"
                                   "result component."),
            # The default for the file is handled by the test object.
            yc.StrElem("file", default='run.log',
                       help_text="Path to the file that this result parser "
                                 "will examine.")
        ]

    @property
    def path(self):
        """The path to the file containing this result parser plugin."""

        return inspect.getfile(self)

    def help(self):
        """Return a formatted help string for the parser."""

        # TODO: have this return argument help too.
        return self.__doc__

    def activate(self):

        config_items = self.get_config_items()

        format.TestConfigLoader.add_result_parser_config(self.name,
                                                         config_items)

        global _RESULT_PARSERS

        if self.name in _RESULT_PARSERS:
            other = _RESULT_PARSERS[self.name]
            if self.priority > other.priority:
                LOGGER.info("Result parser '{}' at {} is superseded by {}."
                            .format(self.name, other.path, self.path))
                _RESULT_PARSERS[self.name] = self
            elif self.priority < other.priority:
                LOGGER.info("Result parser '{}' at {} is ignored in lieu of "
                            "{}.".format(self.name, self.path, other.path))
            else:
                raise RuntimeError("Result parser conflict. Parser '{}' at {}"
                                   "has the same priority as {}"
                                   .format(self.name, other.path, self.path))
        else:
            _RESULT_PARSERS[self.name] = self

    def deactivate(self):

        # Remove the section from the config.
        format.TestConfigLoader.remove_result_parser_config(self.name)

        # Remove from list of available result parsers.
        del _RESULT_PARSERS[self.name]
