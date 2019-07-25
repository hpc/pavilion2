# Yaml Config

YamlConfig allows for the definition of strict configuration formats in YAML
using a structure inspired by ORM database libraries like SQL Alchemy and 
Django. It provides config type enforcement, helpful error messaging, 
config layering (like host/mode/test configs), and the automatic 
generation of config templates.

Pavilion uses YamlConfig to define the test configuration format as well as
the `base pavilion.yaml` file. Hooks are also provided for plugins to add 
additional configuration sections and components to the test config format
dynamically. This documentation covers the basic usage of these hooks, and 
everything you need to know to add components in relevant plugins. 

YamlConfig does not use the standard YAML library, and provides it's own. 
This modified libyaml supports adding comments to generated YAML files, and 
breaks a few conventions. Namely, mapping/dict keys are always ordered, 
either through `collections.OrderedDict` or the base `dict` type in python 3.6+.

## YamlConfig under Pavilion

__The Golden Rule__

_You can add any structure of lists and mappings/dicts to the Pavilion test 
configs, as long as the final holding value elements are always strings._

It's up to the plugins themselves to check and parse these values 
into the final type needed.  This goes a bit against the point of YamlConfig,
but allows Pavilion to have variable insertion (almost) everywhere in the 
test config.

### A Generic Example

YamlConfig definitions consist of a nested _Config Element_ instance 
definitions. The base class for all of these is yaml_config.ConfigElement`


```python
from pavilion.test_config.file_format import TestConfigLoader

# It's convention to import yaml_config as the and rename it as `yc`.
import yaml_config as yc 

# The base plugin class will add the subsection (or results subsection), for 
# you, we do it here to show how it's happening behind the scenes through a 
# class method on the TestConfigLoader
TestConfigLoader.add_subsection(
    # This subsection is a mapping with well defined keys.
    yc.KeyedElem(
        # The first argument is the name of the element, which sets
        # the name in the parent KeyedElem (dict/mapping). 
        "squirrel",
        # Comment to put at the top of this dict when writing a template.
        help_text="Describe the relevant test squirrel",
        # These are the allowed keys of this mapping.
        elements=[
            yc.StrElem(
                'species', 
                default='Abert\'s Squirrel'),
            # RegexElements also produce a string, they just check it against
            # a regex first.
            yc.RegexElem(
                'name',
                regex=r'[a-z]+',
            ),
            yc.StrElem(
                'color',
                # You can limit the choices to a given set of values. 
                choices=['red', 'grey', 'brown']
            ),
            # The nuts key is a list of zero or more nut strings. 
            yc.ListElem(
                name='nuts',
                # The sub_element doesn't require a name, since it's parent
                # isn't a keyed element. It will get a name automatically based 
                # on it's position in the gern
                sub_elem=yc.StrElem()
            ),
        ]
    )
)
```

The resulting config file might look like.
```yaml

mytest:
  run:
    cmds: "echo 'this is still a test config, just with an extra section.'"
  
  # note that this whole section is optional, since it wasn't marked as required
  squirrel:
    name: bob
    color: red
    nuts:
      - hazel
      - pecan
```

Woah, that was a lot to take in. Let's break it down a bit.

### Adding a Subsection
Above we used the TestConfigLoader class to add the subsection directly. 
_You'll never have to do that._

Instead, you'll rely on the plugin base class to do it for you.

```python
from pavilion import schedulers
import yaml_config as yc

class MyScheduler(schedulers.SchedulerPlugin):
    # In scheduler plugins, you have to override this method to return
    # the section's yaml_config element. The scheduler's activate() method
    # handles adding it to the config.
    def get_config(self):
        return yc.KeyedElem(
            # And all the parts of this like above.
        )
```

Result Parser config sections are added [similarly](result_parsers.md#foo).

### Keyed Elements
The `KeyedElem` config elements cause the config to expect a mapping. 

