import pathlib
import re

import yc_yaml as yaml
from .elements import ConfigElement


class ScalarElem(ConfigElement):
    def __init__(self, name=None, **kwargs):
        super().__init__(name=name, _sub_elem=None, **kwargs)

    def _represent(self, value):
        """ We use the built in yaml representation system to 'serialize'
        scalars.
        :returns (value, tag)"""
        # Use the representer from yaml to handle this properly.
        node = self._representer.represent_data(value)
        return node.value, node.tag

    def yaml_events(self, value, show_comments, show_choices):
        # Get our serialized representation of value, and return it as a
        # ScalarEvent.

        tag = None
        if value is not None:
            value, tag = self._represent(value)

        return [yaml.ScalarEvent(value=value, anchor=None, tag=tag,
                                 implicit=(True, True))]

    def find(self, dotted_key):
        if dotted_key != '':
            raise KeyError("Scalars don't have sub-elements, so the only "
                           "valid find  string is '' for them.")

        return self

    def set_default(self, dotted_key, value):
        # We call this just to throw the error for an invalid key.
        self.find(dotted_key)
        self.validate(value)
        self._default = value


class IntElem(ScalarElem):
    """An integer configuration element."""
    type = int


class FloatElem(ScalarElem):
    """A float configuration element."""
    type = float


class RangeElem(ScalarElem):

    def __init__(self, name=None, vmin=None, vmax=None, **kwargs):
        """
        :param vmin: The minimum value for this element, inclusive.
        :param vmax: The max value, inclusive.
        """
        super(RangeElem, self).__init__(name=name, choices=[vmin, vmax],
                                        **kwargs)

    def _choices_doc(self):
        if self._choices == (None, None):
            return None
        elif self._choices[0] is None:
            return 'Valid Range: < {}'.format(self._choices[1])
        elif self._choices[1] is None:
            return 'Valid Range: > {}'.format(self._choices[0])
        else:
            return 'Valid Range: {} - {}'.format(*self._choices)

    def _check_range(self, value):
        if self._choices[0] is not None and value < self._choices[0]:
            raise ValueError("Value {} in {} below minimum ({}).".format(
                value,
                self.name,
                self._choices[0]
            ))
        if self._choices[1] is not None and value > self._choices[1]:
            raise ValueError("Value {} in {} above maximum ({}).".format(
                value,
                self.name,
                self._choices[1]
            ))


class IntRangeElem(IntElem, RangeElem):
    """An int element with range validation."""
    pass


class FloatRangeElem(FloatElem, RangeElem):
    """A float with range validation."""
    pass


class BoolElem(ScalarElem):
    """A boolean element. YAML automatically translates many strings into
    boolean values."""
    type = bool


class StrElem(ScalarElem):
    """A basic string element."""
    type = str

    @staticmethod
    def type_converter(value):

        if isinstance(value, (str, int, bool, float)):
            return str(value)

        raise ValueError(
            "Expected a string (or something trivially convertable to a "
            "string). Got a '{}' with value '{}'"
            .format(type(value), value)
        )


class PathElem(ScalarElem):
    """An element that always expects a filesystem path."""
    type = pathlib.Path


class RegexElem(StrElem):
    """Just like a string item, but validates against a regex."""

    def __init__(self, name=None, regex='', **kwargs):
        """
        :param regex: A regular expression string to match against.
        """

        self.regex = re.compile(regex)
        super(RegexElem, self).__init__(name=name, choices=[regex], **kwargs)

    def _check_range(self, value):

        if self.regex.match(value) is None:
            raise ValueError(
                "Value {} does not match regex '{}' for {} called '{}'".format(
                    value, self._choices[0], self.__class__.__name__, self.name
                ))

    def _choices_doc(self):
        return "Values must match: r'{regex}'".format(regex=self._choices[0])
