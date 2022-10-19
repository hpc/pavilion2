# ext_print: 65
"""yaml_config is a set of utilities for strictly describing a YAML
configuration file, loading it, and validating that the contents conform to
the description. It is also capable of taking the description and
automatically producing an example configuration in the specified format,
complete with comments.

Configuration descriptions are built much like with Object Relational
Mappers (ORMs) for databases. Unlike databases, YAML files are expected to
have nested information that makes the typical ORM syntax unsuitable. Our
solution does it's best to mimick ORM style where possible, while still
allowing for deeply nested configs.

## pyYAML
This library uses an included, modified version of pyYAML capable of building
YAML event sequences that include comments. It is limited to working in pure
python mode only.

# Basic Usage
YamlConfigs consist of ConfigElement() instantiations attached to
container ConfigElement instantiations. These provide the structure
that is used to describe, parse, and output the configuration file. These are
all contained within a user defined subclass of YamlConfig, which is really
just a strictly keyed dictionary ConfigElement with some extras.

    import yaml_config as yc

    class BirthdayPartyConfig(yc.YamlConfigLoader):
        # A list of the valid ConfigElement keys for this config.
        ELEMENTS = [
            # This defines a 'balloons' key, with a default of 0 that must be
            # an int.
            yc.IntElem(
                'balloons',
                default=0,
                help_text='Number of balloons needed'),
            # This defines a 'party_name' key, which can be any string,
            # but is required.
            yc.StrElem(
                'party_name',
                required=True,
                help_text='What to call this party.'),
            # Most types can be limited to specific choices or ranges.
            yc.StrElem(
                'cake',
                default='chocolate', choices=['chocolate', 'vanilla']),
        ]

    # Instantiate the party class. This can be reused to parse multiple configs.
    party = BirthdayPartyConfig()
    config_file = open('party.yaml')
    try:
        # The party object doesn't represent the data, that's returned as a
        # special dictionary.
        party_data = party.load(config_file)
    except ValueError, KeyError, yc.RequiredError:
        print("Oh no, it's a bad party.)

    # All the returned dictionaries are
    balloons = party_data[balloons]
    name = party_data.name

The above configuration description can also produce an actual
configuration file:
"""


from yc_yaml import YAMLError
from .elements import (
    ConfigDict,
    ConfigElement,
    RequiredError,
)
from .loaders import (
    CatYamlConfigLoader,
    ListYamlConfigLoader,
    YamlConfigLoader,
    YamlConfigLoaderMixin,
)
from .scalars import (
    BoolElem,
    FloatElem,
    FloatRangeElem,
    IntElem,
    IntRangeElem,
    PathElem,
    RangeElem,
    RegexElem,
    ScalarElem,
    StrElem,
)
from .structures import (
    ListElem,
    KeyedElem,
    CategoryElem,
    DerivedElem,
)

__all__ = [
    'BoolElem',
    'CatYamlConfigLoader',
    'CategoryElem',
    'ConfigDict',
    'ConfigElement',
    'DerivedElem',
    'FloatElem',
    'FloatRangeElem',
    'IntElem',
    'IntRangeElem',
    'KeyedElem',
    'ListElem',
    'ListYamlConfigLoader',
    'RangeElem',
    'RegexElem',
    'RequiredError',
    'ScalarElem',
    'StrElem',
    'YAMLError',
    'YamlConfigLoader',
    'YamlConfigLoaderMixin',
]
