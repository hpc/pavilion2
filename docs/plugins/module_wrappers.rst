.. _plugins.module_wrappers:

Module Wrapper Plugins
======================

Module Wrappers allow you to override the default modulefile loading
behavior in Pavilion scripts. This can be as simple as setting
additional environment variables, to completely changing what module
systems are supported.

This is often necessary for tests to be generically usable across multiple
systems. Pavilion assumes you're working from a clean 'fresh login'
environment, but that can mean very different things from system to system.
In many cases this means no modules are loaded, while in others a wide swath
may be loaded already that can't be simply purged without breaking the module
system entirely. Differences in module naming may also be an issue from
system-to-system. In these and many other cases, module wrappers allow you to
customize module handling behavior for select modules in a way that smooths
out these differences.

.. contents::

How it Works
------------

Whenever Pavilion is told to load, update, or remove a modulefile in a
Pavilion test config's *run* or *build* sections, a Module Wrapper is
used to generate the commands needed to do so.

It is designed to support both lmod and 'environment modules' (the similar tcl
based system).

1. Find the Module Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~

The name and version of the module to load are used to look up the
correct Module Wrapper plugin. If no such Module Wrapper exists (or no
specific version was requested), Pavilion matches against un-versioned
wrappers. Finally, a generic Module Wrapper is used.

2. Make the Module Change
~~~~~~~~~~~~~~~~~~~~~~~~~

The module wrapper will be used to insert three things into the run or builds
script.

1. One or more lines to load/remove/swap modules.

   - ``module load gcc/7.4.0``
2. One or more lines to validate that this change was successful.

   - ``verify_module_loaded gcc/7.4.0``
   - This is a Pavilion helper function.
3. One or more lines to set additional environment variables.

   - ``export CC=gcc``
   - The default module wrapper doesn't export any environment variables.

Creating a Module Wrapper Ecosystem
-----------------------------------

With a few module wrappers, you can provide an ecosystem by which your tests
will work on any of your systems, regardless of the subtle differences in the
module systems between the hosts.

Typically, this primarily involves writing module wrappers for your main
compilers and MPI modules, and setting a consistent set of environment variables
for each.

For instance, you could set a *PAV_CC*, *PAV_CPP*, and *PAV_FORTRAN*
environment variable in your module wrappers for each compiler, and then
use that to set *CC* in the 'build.env' section of your tests.

Module wrappers allow this to work even if the compiler invocation varies
between systems, such as when one system (cray) uses a compiler wrapper while
others do not.

Writing Module Wrapper Plugins
------------------------------

Everything documented in :ref:`plugins.basics` applies here, so you should
read that first.

Result Parser Class
~~~~~~~~~~~~~~~~~~~

You first must define a Yapsy plugin class, as per the basic instructions.

.. code-block:: python

    # This module has the module_wrapper base plugin class
    import pavilion.module_wrapper as module_wrapper

    # You'll also need ordered dictionaries and the module action helpers.
    from collections import OrderedDict
    from pavilion.module_actions import ModuleLoad, ModuleSwap, ModuleUnload

    class GccWrapper(module_wrapper.ModuleWrapper):
        def __init__(self):

            # You must call the __init__ of the parent class with basic
            # information.
            super().__init__(
                # Whenever you list 'gcc' as a module to use, this will be used.
                name='gcc',
                description="Wrapper for the GCC module",
                # The version is optional. If given, this wrapper will only be
                # used for that specific version of this module.
                version=None)

Changing Module Behavior
~~~~~~~~~~~~~~~~~~~~~~~~

There are three methods you can override to change module handling behavior:

- ``_load()``
- ``_unload()``
- ``_swap()``

These will be called for the corresponding module environment changes. You can
probably get away with only re-defining 'load' in most cases, as swapping and
removal are fairly under Pavilion.

Return Values
^^^^^^^^^^^^^

Pavilion expects that ModuleWrappers return a list of 'actions' and a
dictionary of environment changes.

Most of the 'actions' should be done with ``ModuleAction`` objects. ``ActionLoad``,
``ActionUnload``, and ``ActionSwap`` are available.
Pavilion will convert these automatically into a reasonable sequence of
shell commands to load/unload/swap your modules, and check that the action was
successful. These commands will be inserted directly into your test build and
run scripts.

You may also include shell command strings directly in the list.

Actions generally take the name of the module to manipulate and its version.
To use the default version, or if the module is un-versioned, simply pass
``None``.

.. code-block:: python

    def _load(self, var_man, version):

        # In this
        actions = [
            # Load the gcc module as normal
            ActionLoad(self.name, version)
            # But also the default version of the gcc-helpers module.
            ActionLoad('gcc-helpers', None)
            # And add this command too.
            '. /usr/share/compiler_wrappers'
        ]

        # Return the list of actions, and empty dict of environment changes
        return actions, {}


Variable Manager
^^^^^^^^^^^^^^^^

The 'Variable Manager' is an object that can look up any Pavilion variable
for the test, as per '{{sys.sys_name}}' in a Pavilion config. This allows you
to change module loading behavior based on any variables available to the test.

.. code-block:: python

    def _load(self, var_man, version):

        actions = []

        # The variable manager works a lot like a dictionary
        # You could also use just 'sys_name'
        if var_man['sys.sys_name'] == 'fire_weasel':
            # On this (cray) system, swap out the cray programming environment
            # before switching to the requested gcc.
            actions.extend([
                ActionSwap('PrgEnv-Cray', None, 'PrgEnv-gnu', None)
                ActionSwap(
                    module_name=self.name,
                    version=version,
                    old_module_name=self.name,
                    old_version=None)])
        elif var_man.get('sys.sys_arch') == 'aarch64':
            raise ModuleWrapperError(
                "Module {} is not available on this system".format(self.name))
        else:
            actions.append(ActionLoad(self.name, version))

        return actions, {}


Version
^^^^^^^

The 'version' argument to ``_load()``/``_unload()``/``_swap()`` is the
version the user asks for in the modules section in the test config. For
instance, ``modules: ['gcc/2.2']`` would result in '2.2' being passed. If the
module doesn't have a version, that can either be because the module is
un-versioned, or because the user wants the default version.

Adding to the Environment
~~~~~~~~~~~~~~~~~~~~~~~~~

You can also alter environment variables when writing a module wrapper. The
second return value is a dictionary of these changes. Each key in the
dictionary is the variable name to be exported, and the value is what it will
be set to. Values of ``None`` will unset the variable. All of this is written
as a sequence of ``export``/``unset`` bash commands in the run or build
scripts.

Since the values are written directly to the scripts, they can include any
'bashisms', including referencing other environment variables and subshell
commands.

Your environment variables can depend on each other too. Python 3.5+ (which
is what Pavilion supports) has implicit dictionary ordering, which means the
environment variables will be added to the config in the order you add them
to the dictionary.

.. code-block:: python

    def _load(self, var_man, version):

        actions = [ActionLoad(self.name, version)]

        env = {}
        env['PAV_CC'] = 'gcc'
        env['PAV_CPP'] = 'g++'

        return actions, env

A Full Example
~~~~~~~~~~~~~~

.. code-block:: python

    import pavilion.module_wrapper as module_wrapper
    from pavilion.module_actions import ModuleLoad, ModuleSwap, ModuleUnload

    class GccWrapper(module_wrapper.ModuleWrapper):
        def __init__(self):
            # This is a wrapper for gcc, for any version.
            super().__init__('gcc',
                             "Wrapper for the GCC module",
                             None,
                             self.PRIO_COMMON)

        def _load(self, var_man, version):

            actions = list()
            env = {}

            if var_man['sys_os.name'] == 'cle':
                if var_man['sys_arch'] == 'aarch64'
                    # These systems have the cray programming environment loaded
                    # by default. Swap it out for gnu.
                    actions.append(ModuleSwap('PrgEnv-gnu', None,
                                              'PrgEnv-Cray', None))
                else:
                    # These systems have the intel programming environment
                    # loaded by default. Swap it out for gnu.
                    actions.append(ModuleSwap('PrgEnv-gnu', None,
                                              'PrgEnv-intel', None))

                # Swap out default gcc for the one specified.
                actions.append(ModuleSwap(self.name, version,
                                          self.name, None))

                # Use the cray compiler wrappers
                env['PAV_CC'] = '$(which cc)'
                env['PAV_CXX'] = '$(which CC)'
                env['PAV_FC'] = '$(which ftn)'
            else:
                # Other system start with an empty module environment, so
                # just load the given module.
                actions.append(ModuleLoad(self.name, version))
                env['PAV_CC'] = '$(which gcc)'
                env['PAV_CXX'] = '$(which g++)'
                env['PAV_FC'] = '$(which gfortran)'


            return actions, env

