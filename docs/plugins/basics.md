# Plugins
The majority of Pavilion works via several plugin systems. This documentation
describes how to work with and debug Pavilion plugins in general.

## Plugin Files
As mentioned in the general [config](../config.md) documentation, Pavilion can 
have several configuration directories. Within each of these there can be a 
`plugins/` directory. While Pavilion organizes plugins in sub-directories by 
type (`/schedulers`, `/module_wrappers`, `/commands`, `/sys_vars`, `/results`), 
they can be arranged however you like under `plugins/`.

Regardless of how they're organized, plugins require at least two files to work:
 - <plugin_name>.py - A python module containing the plugin code.
 - <plugin_name>.yapsy-plugin - A config file that describes the plugin.
 
These files must be in the same directory.
 
### <plugin_name>.yapsy-plugin
Here's the slurm.yapsy-plugin file for Pavilion's slurm plugin, with added 
comments.

```ini
[Core]
# The display name of the plugin
Name = Slurm Scheduler
# The name of the module to load (in this directory) to find the plugin.
Module = slurm

# You should fill this out for your plugins, for attribution purposes.
# It is not currently used or visible within Pavilion, however.
[Documentation]
Description = Slurm scheduler wrapper.
Author = Nicholas Sly/Paul Ferrell
Version = 1.0
# We leave this blank, since it's part of the base pavilion code.
Website = 
```

The most important thing here is the `Module` option, which tells the plugin 
manager _which_ python module to load to find the plugin. It's ok if this is 
named the same as other plugins elsewhere.

### <plugin_name>.py

Every plugin needs an associated python module, and that module can contain 
one and only one plugin.

Here's a plugin module for the default sys_name plugin under sys_vars, with 
extra notes:
```python
# Always import the containing module for the plugin base class,and reference 
# the plugin via that. 
import pavilion.system_variables as system_plugins

import subprocess

# You can call your plugin whatever you like, as long as it inherits
# from the base plugin class. The type/category of plugin is determined by 
# the what it inherits from.
class SystemName( system_plugins.SystemPlugin ):

    # Every plugin init should take self and nothing else.
    # No arguments (other than self) will be passed.
    def __init__( self ):
    
        # You MUST call the super classes __init__.
        super().__init__(
            # Every plugin has some sort of name attribute. Regardless of
            # everything else, this defines the name of the plugin.
            plugin_name='sys_name', 
            # This is displayed when listing plugins of this type.
            help_text='The system name (not necessarily hostname).',
            # Plugins with the same name will override others with lower
            # priorities (PRIO_CORE is the lowest)
            priority=self.PRIO_CORE,
            # These define the properties for this plugin type.
            is_deferable=False, 
            sub_keys=None )

    # Most plugins require that you override only a single method.
    def _get( self ):
        """Base method for determining the system name."""

        name = subprocess.check_output(['hostname', '-s'])
        return name.strip().decode('UTF-8')
```

#### Plugin Base Class
As mentioned above, always import the module for the plugin's base class, and
never the base class itself. Yapsy uses the first class it finds that 
inherits from YapsyPlugin to be THE plugin for this module, and may mistake 
the base class for your actual plugin.

The base class you inherit from determines the type/category of the plugin.

#### Plugin Priorities
Most plugins have a priority attribute. If two plugins have the same name, 
this tells Pavilion which one to use. Each priority is an integer (higher is 
better), so you can define plugins that are between these categories as well.

 - PRIO_CORE (0) - The lowest priority, for built-in plugins only.
 - PRIO_COMMON (10) - The default priority, for plugins shared amongst users.
 - PRIO_USER (20) - This is for plugins, typically in your 
 `~/.pavilion/plugins` directory, that should override all others.
 
__NOTE:__ Unlike with test configs and src, the order of the 
config_directories does not matter when resolving conflicting plugins. See 
the [plugin priority](#plugin-priorities) section below.
 
#### Plugin Help
All plugin types have a `description` attribute to describe the plugins 
when listed with the appropriate `pav show` command.

## Debugging Plugins
When you write your first plugin, odds are it won't show up when you try to 
list or use it. This is generally due to an error in your python code or an 
error loading the plugin. 

### Check your config directories
Run `pav show config` to print your Pavilion config, and check your list of 
'config_dirs', your plugin should be in the plugins directories under one of 
those paths.

### Check the .yapsy-plugin file
The `Module` option (under `[Core]`) should match your plugin's module name.

### Check the Logs
Any errors should show up in your 
`<working_dir>/pavilion.log`, but in a few cases even that will be silent. 
Those cases are considered to be bugs, and you should report them.

### Run Your Plugin
Run your plugin as a python module.

```bash
$ export PYTHONPATH=<Pavilion''s lib directory>
$ cd <your plugin dir>
$ python3
>>> import myplugin
>>> myplugin.MyPluginClass()
```

The plugin module should be able to run and you should be able to create an
instance without throwing an error.
