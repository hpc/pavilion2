Getting Started
===============

Yaml Config is a set of utilities for strictly describing a YAML configuration file,
loading it, and validating that the contents conform to the specification. It is also
capable of taking the description and automatically producing an example configuration
in the specified format, complete with comments.

Configuration specifications are built much like with Object Relational Mappers (ORMs)
for databases. Unlike databases, YAML files are expected to have nested information
that makes the typical ORM syntax unsuitable. Our solution does it's best to mimic
ORM style where possible, while still allowing for the deeply nested config variables
that YAML provides.

A note on pyYAML
------------------
This library uses an included, modified version of pyYAML capable of building
YAML event sequences that include comments. It is limited to working in pure python
mode only.

Basic Usage
-----------

Yaml Configs consist of ConfigElement() instantiations attached to
container ConfigElement instantiations. These provide the structure
that is used to describe, parse, and output the configuration file. These are
all contained within a user defined subclass of Yaml Config, which is really
just a strictly keyed dictionary ConfigElement with some extras.::

    import yaml_config as yc

    class BirthdayPartyConfig(yc.YamlConfigLoader):
        # A list of the valid ConfigElement keys for this config. A list is used to preserve
        # the element order.
        ELEMENTS = [
            # This defines a 'balloons' key, with a default of 0 that must be an int.
            yc.IntElem('balloons', default=0, help_text='Number of balloons needed'),

            # This defines a 'party_name' key, which can be any string, but is required.
            yc.StrElem('party_name', required=True, help_text='What to call this party.'),

            # Most types can be limited to specific choices or ranges.
            yc.StrElem('cake', default='chocolate', choices=['chocolate', 'vanilla']),
        ]

    # Instantiate the party class. This can be reused to parse multiple configs.
    party = BirthdayPartyConfig()
    config_file = open('party.yaml')
    try:
        # The party object doesn't represent the data, that's returned as a
        # special dictionary.
        party_data = party.load(config_file)
    except ValueError, KeyError, yc.RequiredError:
        print("Oh no, it's a bad party.")
        raise

    # All the returned dictionaries are class yaml_config.ConfigDict, which allows for
    # attribute references.
    balloons = party_data[balloons]
    name = party_data.name

This config description will happily accept a YAML document that looks like: ::

    party_name: Armond White's Movie Party
    balloons: 5
    cake: chocolate

The example file produced looks like: ::

    # BALLOONS(int): Number of balloons needed
    balloons:
    # PARTY_NAME(required str): What to call this party.
    party_name:
    # CAKE(str)
    # Choices: chocolate, vanilla
    cake:

You can also give the config data to YamlConfigLoader.dump(), which will produce a filled out
configuration.

Restrictions and Limitations
-----------------------------
Yaml Config does not preserve formatting end to end. While it will read any valid YAML file (and
validate any that conform to a config specification), it will not preserve the formatting if it
subsequently re-dumps the same data.

Additionally, there are a few format restrictions that Yaml Config imposes:

 * Because Yaml Config allows loaded data keys to be accessed through attributes (ie `data.key1`),
   only keys that are valid python identifiers are allowed. The regex is `r'[a-z][a-z0-9_]'`.
 * Keys read from files are treated as case insensitive, and are always referred to in lowercase.
 * For Lists and Category elements, the types of each entry must be the same.

 * Validation/format enforcement occurs on data load. You can separately validate before
   dumping using your config objects `.validate(data)` method.

