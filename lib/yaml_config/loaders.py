from abc import ABCMeta, abstractmethod

import yc_yaml as yaml
from .structures import ListElem, KeyedElem, CategoryElem


class YamlConfigLoaderMixin:
    """Converts a ConfigElement class into a class that also knows how to
    load and dump the configuration to file. A class variable of some sort,
    to be overridden by the class end-user, is expected to hold the
    information to initialize the ConfigElement base. Only KeyedElem,
    CategoryElem, and ListElem really make since as bases to mix this
    in with."""

    # Note below that the method resolution order in the classes that call
    # YamlConfigMixin method last. That's needed to make it easy to call the
    # ConfigElem classes' __init__ method easily, but also to ensure that the
    # abstract methods in this mixin are ignored, as they must be.

    __metaclass__ = ABCMeta

    HEADER = ""

    # This is expected to be overridden by the main class.
    type = None

    def dump(self, outfile, values=None,
             show_comments=True, show_choices=True):
        """Write the configuration to the given output stream.

        :param stream outfile: A writable stream object
        :param {} values: Write the configuration file with the given values
            inserted. Values should be a dictionary as produced by
            YamlConfigLoader.load().
        :param bool show_comments: When dumping the config file, include
            help_text and general element information as comments.
            Default True.
        :param bool show_choices: When creating comments, include the
            choices available for each item. Default True.
        """

        # We're recursively generating a list of pyYaml events, which will
        # then be emitted to create the yaml file. Each element knows how to
        # represent itself and how to include any child elements.
        events = list()
        events.extend([yaml.StreamStartEvent(), yaml.DocumentStartEvent()])
        events.extend(self.yaml_events(values, show_comments, show_choices))
        events.extend([yaml.DocumentEndEvent(), yaml.StreamEndEvent()])

        yaml.emit(events, outfile)

    def load(self, infile, partial=False):
        """Load a configuration YAML file from the given stream, and then
        validate against the config specification.

        :param stream infile: The input stream from which to read.
        :param bool partial: The infile is not expected to be a complete
            configuration, so missing 'required' fields can be ignored.
        :returns ConfigDict: A ConfigDict of the contents of the configuration
            file.
        :raises IOError: On stream read failures.
        :raises YAMLError: (and child exceptions) On YAML format issues.
        :raises ValueError, RequiredError, KeyError: As per validate().
        """

        raw_data = yaml.load(infile)

        values = self.normalize(raw_data)

        return self.validate(values, partial=partial)

    @staticmethod
    def load_raw(infile):
        """Load the raw config. This just does a yaml.load with no
        validation. You're expected to validate separately."""

        return yaml.load(infile)

    def load_empty(self, partial=True):
        """Get a copy of the configuration, as if we had loaded an empty file.
        Essentially, get a configuration with just the defaults.

        :param bool partial: The config is not expected to be complete.
        :returns ConfigDict: A ConfigDict of the contents of the configuration
            file.
        :raises ValueError, RequiredError, KeyError: As per validate().
        """

        return self.validate(self.type(), partial=partial)

    def load_merge(self, base_data, infile, partial=False):
        """Load the data infile, merge it into base_data, and then validate the
            combined result.
        :param base_data: Existing data to merge new data into.
        :param file infile: The input file object.
        :param bool partial: The infile is not expected to be a complete
        configuration, so missing 'required' fields can be ignored.
        :returns ConfigDict: A ConfigDict of the contents of the configuration
            file.
        :raises IOError: On stream read failures.
        :raises YAMLError: (and child exceptions) On YAML format issues.
        """

        new_data = yaml.load(infile)

        new_data = self.normalize(new_data)

        data = self.merge(base_data, new_data)

        return self.validate(data, partial=partial)

    def merge(self, old, new):
        """This should be overridden by the element class."""
        raise NotImplementedError

    @abstractmethod
    def yaml_events(self, values, show_comments, show_choices):
        """This is expected to be defined by the co-inherited ConfigElement
        type."""
        return [values, show_comments, show_choices]

    @abstractmethod
    def validate(self, data, partial=False):
        """This is expected to be defined by the co-inherited ConfigElement
            type."""
        _ = partial

        return data

    @abstractmethod
    def normalize(self, values):
        """This will be overridden."""
        return values

    @abstractmethod
    def find(self, dotted_key):
        """This is expected to be defined by the co-inherited ConfigElement
        type."""
        return dotted_key

    def set_default(self, dotted_key, value):
        """Sets the default value of the element found using dotted_key path.
        See the structure of the elements relative to this one, which is
        typically the base ConfigElement instance. Each component of the
        dotted key must correspond to a named key at that level. In cases
        such as lists where then sub_elem doesn't have a name, a '*' should
        be given.

        Why ever use this? Because in many cases the default is based on
        run-time information.

        Examples: ::

            class DessertConfig(yc.YamlConfigLoader):
                ELEMENTS = [
                    yc.KeyedElem('pie', elements=[
                        yc.StrElem('fruit')
                    ]
                ]

            config = DessertConfig()

            # Set the 'fruit' element of the 'pie' element to have a
            # default of 'apple'.
            config.set_default('pie.fruit', 'apple')

            class Config2(yc.YamlConfigLoader):
                ELEMENTS = [
                    yc.ListElem('cars', sub_elem=yc.KeyedElem(elements=[
                        yc.StrElem('color'),
                        yc.StrElem('make')
                    ]
                ]

                def __init__(self, default_color):
                    # The Config init is a good place to do this.
                    # Set all the default color for all cars in the 'cars'
                    # list to red.
                    config.set_default('cars.*.color', 'red')

                    super(self, Config2).__init__()

        :param str dotted_key: The dotted key path to the element to set
            the default on.
        :param value: The value to set the default to. This validated.
        :raises ValueError: If the default fails validation.
        :return: None
        """

        # The ConfigElement's find method does all the heavy lifting.
        elem = self.find(dotted_key)
        elem.default = value


class YamlConfigLoader(KeyedElem, YamlConfigLoaderMixin):
    """Defines a YAML config specification, where the base structure is a
    strictly keyed dictionary.

    To use this, subclass it and override the ELEMENTS class variable with a
    list of ConfigElement instances that describe the keys for config. ::

        import yaml_config as yc

        class StrictConfig(yc.YamlConfigLoader):
            # These are the only keys allowed.
            ELEMENTS = [
                yc.StrElem('first_name', required=True),
                yc.StrElem('last_name', required=True),
                yc.RegexElem('middle_initial', regex=r'[A-Za-z]'),
                yc.IntRangeElem('age', vmin=1, required=True)
            ]

    A valid config could look like: ::
        first_name: Bob
        last_name: Sagat
        age: 59

    :cvar [str] HEADER: The documentation that should appear at the top of the
        config file.
    :cvar [ConfigElement] ELEMENTS: Override this with a list of element
        types describing your configuration.
    """

    ELEMENTS = []

    def __init__(self, name='<root>'):
        """Initialize the config."""
        super(YamlConfigLoader, self).__init__(
            elements=self.ELEMENTS, help_text=self.HEADER)
        # The name checking in __init__ will reject this name if set normally.
        self.name = name


class CatYamlConfigLoader(CategoryElem, YamlConfigLoaderMixin):
    """This is just like YamlConfigLoader, except instead of giving a list of
    elements to use as strict keys in a KeyedElem, we get a single BASE to
    use as the type for each sub-element in a CategoryElem.

    Example: ::

        import yaml_config as yc

        class UserConfig(yc.CateYamlConfigLoader):
            # This is the type that each key must conform to.
            BASE = yc.KeyedElem(elements=[
                # We define elements just like for the YamlConfigLoader. As a
                # KeyedElem, these are the only keys allowed
                yc.StrElem('first_name', required=True),
                yc.StrElem('last_name', required=True),
                yc.IntRangeElem('age', vmin=1, required=True)
            ]

    In this case, a valid config can have many users defined: ::

        coulson:
            first_name: Phillip
            last_name: Coulson
            age: 52

        mmay:
            first_name: Melinda
            last_name: May
            age: 54

    :cvar [str] HEADER: The documentation that should appear at the top of
        the config file.
    :cvar ConfigElement BASE: A single ConfigElement describing what all the
        keys at the base level of this config must look like.
    """

    BASE = None

    def __init__(self, name='<root>'):
        super(CatYamlConfigLoader, self).__init__(
            sub_elem=self.BASE, help_text=self.HEADER)
        # The name checking in __init__ will reject this name if set normally.
        self.name = name


class ListYamlConfigLoader(ListElem, YamlConfigLoaderMixin):
    """A YamlConfigLoader where the base element is a ListElem. Like normal
    list elements, all items in the list must have the same element type,
    described by BASE.

    Example: ::

        import yaml_config as yc

        class ShoppingList(yc.ListYamlConfig):
            BASE = yc.StrElem()

    An example 'shopping list' config could look like: ::

        - banannas
        - correctly spelled bananas
        - apples
        - cantaloupe

    :cvar [str] HEADER: The documentation that should appear at the top of
        the config file.
    :cvar ConfigElement BASE: A single ConfigElement describing what each
        item in the base level list of this config must look like.

    """

    BASE = None

    def __init__(self, name='<root>'):
        super(ListYamlConfigLoader, self).__init__(
            sub_elem=self.BASE, help_text=self.HEADER)
        self.name = name
