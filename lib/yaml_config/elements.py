"""
This module defines a set of constructs for strictly defining configuration
objects that get their data from Yaml files. It allows for the general (
though not complete) flexibility of Yaml/Json, while giving the program
using it assurance that the types and structure of the configuration
parameters brought in are what is to be expected. Configuration objects
generated by this library can be merged in a predictable way. Example
configurations can automatically be generated, as can configurations
already filled out with the given values.
"""

import copy
import pathlib
import re
from abc import ABCMeta

import yc_yaml as yaml
from yc_yaml import representer


class RequiredError(ValueError):
    pass


class ConfigDict(dict):
    """Since we enforce field names that are also valid python names, we can
    build this dict that allows for getting and setting keys like attributes.

    The following marks this class as having dynamic attributes for IDE
    typechecking.
    @DynamicAttrs
    """

    def __getattr__(self, key):
        if key in self:
            return super().__getitem__(key)
        else:
            return super().__getattribute__(key)

    def __setattr__(self, key, value):
        if key in self:
            super().__setitem__(key, value)
        else:
            super().__setattr__(key, value)

    def copy(self):
        return ConfigDict(self)


class NullList(list):
    """A list with no extra attributes other than the fact that it is a
    distinct class from 'list'. We'll use this to tell the difference
    between an empty list and a list that is implicitly defined."""

    def copy(self):
        """When we copy this list, make sure it returns another NullList. The
        base list class probably should have probably done it this way."""
        return self.__class__(self)


# Tell yaml how to represent a ConfigDict (as a dictionary).
representer.SafeRepresenter.add_representer(
    ConfigDict,
    representer.SafeRepresenter.represent_dict)


# This is a dummy for type analyzers
def _post_validator(siblings, value):
    # Just using the variables to clear analyzer complaints
    return siblings[value]


class ConfigElement:
    """The base class for all other element types.

    :cvar type: The type object used to type-check, and convert if needed,
        the values loaded by YAML. This must be defined.
    :cvar type_converter: A function that, given a generic value of unknown
        type, will convert it into the type expected by this ConfigElement. If
        this is None, the type object itself is used instead.
    :cvar _type_name: The name of the type, if different from type.__name__.

    """

    __metaclass__ = ABCMeta

    type = None
    type_converter = None
    _type_name = None

    # The regular expression that all element names are matched against.
    _NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]+$')

    # We use the representer functions in this to consistently represent
    # certain types
    _representer = yaml.representer.SafeRepresenter()

    def __init__(self, name=None, default=None, required=False, hidden=False,
                 _sub_elem=None, choices=None, post_validator=None,
                 help_text=""):
        """Most ConfigElement child classes take all of these arguments, and
        just add a few of their own.

        :param str name: The name of this configuration element. Required if
            this is a key in a KeyedElem. Will receive a descriptive default
            otherwise.
        :param default: The default value if no value is retrieved from a config
            file.
        :param bool required: When validating a config file, a RequiredError
            will be thrown if there is no value for this element. *NULL does
            not count as a value.*
        :param hidden: Hidden elements are ignored when writing out the config
            (or example configs). They can still be set by the user.
        :param list choices: A optional sequence of values that this type will
            accept.
        :param post_validator post_validator: A optional post validation
            function for this element. See the Post-Validation section in
            the online documentation for more info.
        :param Union(ConfigElement,None) _sub_elem: The ConfigElement
            contained within this one, such as for ListElem definitions. Meant
            to be set by subclasses if needed, never the user. Names are
            optional for all sub-elements, and will be given sane defaults.
        :raises ValueError: May raise a value error for invalid configuration
            options.
        """

        if name is not None:
            self._validate_name(name)

        self.name = name

        self.required = required
        self.hidden = hidden
        if self.hidden and (default is None and self.required):
            raise ValueError(
                "You must set a default for required, hidden Config Elements.")

        self._choices = choices
        self.help_text = help_text

        # Run this validator on the field data (and all data at this level
        # and lower) when
        # validating
        if not hasattr(self, 'post_validator'):
            self.post_validator = post_validator

        # The type name is usually pulled straight from the type's __name__
        # attribute This overrides that, when not None
        if self._type_name is None:
            self._type_name = self.type.__name__

        # Several ConfigElement types have a sub_elem. This adds an empty
        # one at the top level so we can have methods that work with it at
        # this level too.
        if _sub_elem is not None:
            if not isinstance(_sub_elem, ConfigElement):
                raise ValueError(
                    "Sub-elements must be a config element of some kind. "
                    "Got: {}"
                    .format(_sub_elem))

        self._sub_elem = _sub_elem

        # Set the sub-element names if needed.
        self._set_sub_elem_names()

        # The default value gets validated through a setter function.
        self._default = None
        if default is not None:
            self.default = self.normalize(default)

    def _set_sub_elem_names(self):
        """Names are optional for sub-elements. If one isn't given,
        this sets a reasonable default so that we can tell where errors came
        from."""

        # We can't set names on the sub_elem if we have neither
        if self._sub_elem is None or self.name is None:
            return

        # The * isn't super obvious, but it matches the 'find' syntax.
        if self._sub_elem.name is None:
            self._sub_elem.name = '{}.*'.format(self.name)

        # Recursively set names on sub-elements of sub-elements.
        # pylint: disable=protected-access
        self._sub_elem._set_sub_elem_names()

    def _check_range(self, value):
        """Make sure the value is in the given list of choices. Throws a
        ValueError if not.

        The value of *self.choices* doesn't matter outside of this method.

        :returns: None
        :raises ValueError: When out of range."""

        if self._choices and value not in self._choices:
            raise ValueError(
                "Value '{}' not in the given choices {} for {} called '{}'."
                .format(
                    value,
                    self._choices,
                    self.__class__.__name__,
                    self.name
                ))

    @property
    def default(self):
        return copy.copy(self._default)

    @default.setter
    def default(self, value):
        self.validate(value)
        self._default = value

    def normalize(self, value):
        """Recursively normalize the given value to the expected type.
        :raises TypeError: If the type conversion fails.
        """

        if not isinstance(value, self.type):
            if value is None:
                return None

            try:
                converter = self.type
                if self.type_converter is not None:
                    converter = self.type_converter
                value = converter(value)
            except TypeError:
                raise TypeError("Incorrect type for {} field {}: {}"
                                .format(self.__class__.__name__, self.name,
                                        value))

        return value

    def validate(self, value, partial=False):
        """Validate the given value, and return the validated form.

        :returns: The value, converted to this type if needed.
        :raises ValueError: if the value is out of range.
        :raises RequiredError: if the value is required, but missing.
        """

        if value is None:
            if self._default is not None:
                value = self._default
            elif self.required and not partial:
                raise RequiredError(
                    "Config missing required value for {} named {}."
                    .format(self.__class__.__name__, self.name))
            else:
                return None

        self._check_range(value)

        return value

    def make_comment(self, show_choices=True, show_name=True,
                     recursive=False):
        """Create a comment for this configuration element.

        :param show_name: Whether to show the name of this element.
        :param show_choices: Whether to include the valid choices for this
            item in the help comments.
        :param recursive: The comments should recursively include the help
            for sub elements.
        :returns: A comment string."""

        if self.name is None or self.name.endswith('*'):
            name = ''
        else:
            name = self.name.upper()

        props = []
        if not self.required:
            props.append('opt')

        if self._type_name:
            props.append(self.comment_type_str())

        if props:
            props = '({})'.format(' '.join(props))
        else:
            props = ''

        comments = ['{name}{props}{colon} {help}'.format(
            name=name if show_name else '',
            props=props,
            colon=':' if self.help_text else '',
            help=self.help_text,
        )]

        if show_choices and self._choices:
            comments.append('  ' + self._choices_doc())

        if recursive:
            comments.extend(self.get_sub_comments(
                show_choices=show_choices,
                show_name=show_name
            ))

        return '\n'.join(comments)

    def get_sub_comments(self, show_choices, show_name):
        """Get the comments from any sub elements to add this element's
        comments."""

        sub_comments = []

        if self._sub_elem:
            sub_comments.append(self._sub_elem.make_comment(
                show_choices=show_choices,
                show_name=show_name,
                recursive=True,
            ))

        return sub_comments

    def comment_type_str(self):
        """Return a """
        return self._type_name if self._type_name else ''

    def find(self, dotted_key):
        """Find the element matching the given dotted key. This is useful
        for retrieving elements to use their help_text or defaults.

        Dotted keys look like normal property references, except that the
        names of the sub-element for Lists or Collections are given as a '*',
        since they don't have an explicit name. An empty string always
        returns this element.

        Examples: ::

            class Config2(yc.YamlConfigLoader):
                ELEMENTS = [
                    yc.ListElem('cars', sub_elem=yc.KeyedElem(elements=[
                        yc.StrElem('color'),
                        yc.StrElem('make'),
                        yc.IntElem('year'),
                        yc.CollectionElem(
                            'accessories',
                            sub_elem=yc.KeyedElem(elements=[
                                yc.StrElem('floor_mats')
                        ])
                    ]
                ]

            config = Config2()
            config.find('cars.*.color')

        :param str dotted_key: The path to the sought for element.
        :returns ConfigElement: The found Element.
        :raises KeyError: If the element cannot be found.
        """

        raise NotImplementedError("Implemented by individual elements.")

    def yaml_events(self, value, show_comments, show_choices):
        """Returns the yaml events to represent this config item.
            :param value: The value of this config element. May be None.
            :param int show_comments: Whether or not to include comments.
            :param show_choices: Whether or not to show the choices string
            in the comments.
        """

        raise NotImplementedError(
            "When defining a new element type, you must define "
            "how to turn it (and any sub elements) into a list of "
            "yaml events.")

    def _choices_doc(self):
        """Returns a list of strings documenting the available choices and
        type for this item. This may also return None, in which cases
        choices will never be given."""

        return 'Choices: ' + ', '.join(map(str, self._choices))

    def _validate_name(self, name):
        if name != name.lower():
            raise ValueError(
                "Invalid name for config field {} called {}. Names must "
                "be lowercase".format(self.__class__.__name__, name))

        if self._NAME_RE.match(name) is None:
            raise ValueError(
                "Invalid name for config field {} called {}. Names must "
                "start with a letter, and be composed of only letters, "
                "numbers, and underscores."
                .format(self.__class__.__name__, name))

    # pylint: disable=no-self-use
    def _represent(self, value):
        """Give the yaml representation for this type. Since we're not
        representing generic python objects, we only need to do this for
        scalars."""
        return value

    def _run_post_validator(self, elem, siblings, value):
        """Finds and runs the post validator for the given element.

        :param ConfigElement elem: The config element to run post_validation on.
        :param siblings: The siblings
        """

        # Don't run post-validation on non-required fields that don't have a
        # value.
        # if not elem.required and value is None:
        #    return None

        try:
            if elem.post_validator is not None:
                return elem.post_validator(siblings, value)

            local_pv_name = 'post_validate_{}'.format(elem.name)
            if hasattr(self, local_pv_name):
                getattr(self, local_pv_name)(siblings, value)
            else:
                # Just return the value if there was no post-validation.
                return value
        except ValueError as err:
            # Reformat any ValueErrors to point to where this happened.
            raise ValueError("Error in post-validation of {} called '{}' "
                             "with value '{}': {}"
                             .format(elem.__class__.__name__, elem.name,
                                     value, err))

    # pylint: disable=no-self-use
    def merge(self, old, new):
        """Merge the new values of this entry into the existing one. For
        most types, the old values are simply replaced. For complex types (
        lists, dicts), the behaviour varies."""

        return new

    def __repr__(self):
        return "<yaml_config {} {}>".format(self.__class__.__name__, self.name)
