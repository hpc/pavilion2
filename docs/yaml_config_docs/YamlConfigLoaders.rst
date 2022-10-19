YAML Configs
===============

The Yaml Config classes are subclassed to form the specification for your config file, and form
the root from which loading, writing, and validating configs is performed. The form of this base
depends on which Yaml Config class you use.

Yaml Config
-------------
Yaml Config uses a KeyedElem as the root, resulting in a strictly keyed root dictionary. Each key
must be predefined, but each key may have a unique element type.

.. autoclass:: yaml_config.YamlConfigLoader
    :members: dump, load, validate, find, set_default

Category Yaml Config Loaders
-----------------------------
CatYamlConfigLoader uses a CategoryElem as root, resulting in a dictionary that can have
flexibly defined keys, but the keys must share an element type.  This is for when you know
what each config item will look like, but don't know their names or quantities.

.. autoclass:: yaml_config.CatYamlConfigLoader

List Yaml Config Loaders
-----------------------------

List Yaml Config Loaders have a ListElem as their root, and result in a list as the base of the config
data.

.. autoclass:: yaml_config.ListYamlConfigLoader

Yaml Config Loader Mixin
============================
This mixin converts a ConfigElement class into a YamlConfig-like class, adding
dump and load methods. Unlike most mixins, it should occur after the regular base class
in calling order.

.. autoclass:: yaml_config.YamlConfigLoaderMixin

