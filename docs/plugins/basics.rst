
.. _plugins.basics:

Plugin Basics
=============

The majority of Pavilion works via several plugin systems. This
documentation describes how to work with and debug Pavilion plugins in
general.

.. contents::

Plugin Files
------------

As mentioned in the general :ref:`config` documentation,
Pavilion can have several configuration directories. Within each of
these there can be a ``plugins/`` directory. While Pavilion organizes
plugins in sub-directories by type (``/schedulers``,
``/module_wrappers``, ``/commands``, ``/sys_vars``, ``/results``), they
can be arranged however you like under ``plugins/``.

Regardless of how they're organized, plugins require at least two files
to work: - .py - A python module containing the plugin code. -
.yapsy-plugin - A config file that describes the plugin.

These files must be in the same directory.

.yapsy-plugin
~~~~~~~~~~~~~

Here's the slurm.yapsy-plugin file for Pavilion's slurm plugin, with
added comments.

.. code:: ini

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

The most important thing here is the ``Module`` option, which tells the
plugin manager *which* python module to load to find the plugin. It's ok
if this is named the same as other plugins elsewhere.

.py
~~~

Every plugin needs an associated python module, and that module can
contain one and only one plugin.

Here's a plugin module for the default sys\_name plugin under sys\_vars,
with extra notes:

.. code:: python

    # Always import the containing module for the plugin base class,and reference
    # the plugin via that.
    import pavilion.system_variables as system_plugins

    import subprocess

    # You can call your plugin whatever you like, as long as it inherits
    # from the base plugin class. The type/category of plugin is determined by
    # the what it inherits from.
    class SystemName( system_plugins.SystemPlugin ):

        # Every plugin's init takes self and nothing else.
        # No arguments (other than self) will be passed.
        def __init__(self):

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

Plugin Base Class
-----------------

As mentioned above, always import the module for the plugin's base
class, and never the base class itself. Yapsy uses the first class it
finds that inherits from YapsyPlugin to be THE plugin for this module,
and may mistake the base class for your actual plugin.

The base class you inherit from determines the type/category of the
plugin.

Plugin ``__init__()``
~~~~~~~~~~~~~~~~~~~~~

Every plugin base class in Pavilion provides an ``__init__()`` that must
be overridden. This overridden ``__init__()`` must then call the base
class's ``__init__()`` to define the basic properties of the plugin.

.. code:: python

    # Every plugin requires a simple __init__ that calls the init of the base
    # plugin class.
    class MyPlugin(plugin_module.PluginBaseClasse):
        def __init__(self):
            super().__init__(
                # Every plugin takes this argument
                name='myplugin',
            )

Plugin 'name'
~~~~~~~~~~~~~

Every Pavilion plugin takes a ``name`` argument in the base class's
``__init__()``. Only one plugin with a given ``name`` is allowed, but
conflicts may be resolved using plugin priorities.

Plugin 'priority'
~~~~~~~~~~~~~~~~~

Most plugins have a priority attribute. If two plugins have the same
name, this tells Pavilion which one to use. Each priority is an integer
(higher is better), so you can define plugins that are between these
categories as well.

-  PRIO\_CORE (0) - The lowest priority, for built-in plugins only.
-  PRIO\_COMMON (10) - The default priority, for plugins shared amongst
   users.
-  PRIO\_USER (20) - This is for plugins, typically in your
   ``~/.pavilion/plugins`` directory, that should override all others.

**NOTE:** Unlike with test configs and src, the order of the
config\_directories does not matter when resolving conflicting plugins.

Plugin 'description'
~~~~~~~~~~~~~~~~~~~~

All plugin types have a ``description`` attribute to describe the
plugins when listed with the appropriate ``pav show`` command.

Plugin Initialization
---------------------

Plugins go through the following steps when initialized. This section
details those steps to aid in debugging. Failure or exceptions raised in
any of these steps should be logged to the Pavilion log.

Note that these steps are followed every time Pavilion runs a command.
Most plugin types are lazily evaluated; schedulers won't get scheduler
info until we try to scheduler a job, and sys\_var plugins won't gather
information until we try to resolve variables in a config.

1. Plugin Search
~~~~~~~~~~~~~~~~

Each of the Pavilion config directories is searched in their ``plugins``
directory for plugins. For each ``.yapsy-plugin`` file found, Yapsy will
load that plugin configuration. For Pavilion's purposes, only the
``Module`` config item actually matters.

2. Plugin Module Load
~~~~~~~~~~~~~~~~~~~~~

The value of the plugin's ``Module`` attribute determines which module
(in the same directory) should be loaded to find the Plugin class. If
the module file is found, Yapsy will load it.


3. Finding the Plugin Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yapsy will walk through the plugin module's namespace and find the first
class that inherits from ``yapsy.IPlugin`` (or has an ancestor that
inherits from it.) Hopefully this is your plugin, as your plugin should
inherit from one of the Pavilion plugin base classes which in turn
inherit from ``IPlugin``.

**Note 1:** If you've imported the ``IPlugin`` class or a Pavilion
plugin base class into the module namespace, Yapsy may find that
instead.

**Note 2:** You may create new plugin base classes or inherit from other
plugins, as long as one of the existing Pavilion plugin base classes is
an ancestor.

4. Plugin init
~~~~~~~~~~~~~~

Yapsy will then create an instance of the plugin class. No useful
information can or will be passed to ``__init__()``.

5. Plugin activate
~~~~~~~~~~~~~~~~~~

After an instance of a plugin is created, the ``.activate()`` method is
called. This will add your plugin to the list of known plugins of its
type, and also handles overrides due to priority.

Congratulations, your plugin is now loaded into Pavilion.

Debugging Plugins
-----------------

When you write your first plugin, odds are it won't show up when you try
to list or use it. This is generally due to an error in your python code
or an error loading the plugin.

Pavilion should print information about which
plugins failed to load to stderr whenever you run it, and may also print
the exceptions encountered when loading the plugin. The full plugin path
will be included, so at least you'll know where to look for the issue.

Plugin not listed
~~~~~~~~~~~~~~~~~
This can happen for a couple of reasons.

Symptoms:
 - Your tests are failing due to a bad config related to a module
 - The module isn't listed under the relevant ``module show`` commands.
 - There are no plugin errors shown when run pav.

Probable Causes:
 - You're missing the relevant ``.yapsy-plugin`` file.
 - The plugin files aren't in one of the searched locations. Check the
   **config_dirs** setting under ``pav show config``.
 - The plugin class doesn't inherit from one of the Pavilion plugin classes.
 - You've imported either a Pavilion plugin class or yapsy's IPlugin class
   directly via ``from pavilion.result_parsers import ResultParser`` or
   similar.

"Plugin candidate rejected: cannot find ... module"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pavilion is trying to load your plugin, but the module named in your
``.yapsy-plugin`` file can't be found.

The ``Module`` option (under ``[Core]``) should match your plugin's
module name.

"Unable to create plugin object..."
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
An exception was thrown when running the ``__init__`` or ``activate`` methods
in your plugin. The exact exception should have been printed to screen and the
logs.

"Unable to import plugin..."
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There is an error, probably a syntax error, in your plugin module. This should
contain a message pointing to the exact problem.

Other Errors
~~~~~~~~~~~~

This documentation should include all the known errors Plugins might throw. If
you find any we missed, please report them on the hpc/pavilion2 project on
github.

Run Your Plugin
~~~~~~~~~~~~~~~

When debugging plugins, it's often useful to run them by themselves:

.. code:: bash

    export PYTHONPATH=#<Pavilion's lib directory>
    cd #<your plugin dir>
    python3
    # >>> import myplugin
    # >>> myplugin.MyPluginClass()

The plugin module should be able to run and you should be able to create
an instance without throwing an error.
