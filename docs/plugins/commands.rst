Pavilion Command Plugins
========================

Every Pavilion command is actually a plugin. The command plugin system
provides easy ways to set up command arguments and the functions that
actually perform the command.

.. contents::

Command Plugin Init
-------------------

Every command plugin inherits from the ``pavilion.commands.Command`` plugin
base class. Like all other Pavilion plugin classes, the ``__init__`` method must
take no arguments, and it must call the parent class's ``__init__`` to name
and document the plugin.

.. code:: python

    from pavilion import commands

    class CancelCommand(commands.Command):
        """A basic command class."""

        def __init__(self):
            super().__init__(
                name='cancel',
                description='Cancel tests or series.',
                short_help='Cancel a test, tests, or series.",
                aliases=['kill', 'stop']
            )

Name and Aliases
^^^^^^^^^^^^^^^^
The ``name`` attribute is both the name of this plugin and that users will
use to call this command. The ``aliases`` attribute takes a list of alternate
names for the command. Given the above, all of the following are valid ways
to call our example command.

.. code:: bash

  $ pav cancel
  $ pav kill
  $ pav stop

Help
^^^^
The command ``description`` is printed when running ``pav <cmd> --help``, along
with the rest of the documentation in the command's arguments. The following is
what is printed for the real ``pav cancel`` command.

.. code::

    $ pav cancel --help
    usage: pav.py cancel [-h] [-s] [-j] [tests [tests ...]]

    Cancel a test, tests, or test series.

    positional arguments:
      tests         The name(s) of the tests to cancel. These may be any mix of
                    test IDs and series IDs. If no value is provided, the most
                    recent series submitted by the user is cancelled.

    optional arguments:
      -h, --help    show this help message and exit
      -s, --status  Prints status of cancelled jobs.
      -j, --json    Prints status of cancelled jobs in json format.


The command ``short_help`` is printed when running ``pav --help`` when the
command is listed. If no short help is given, the command will be hidden (but
still usable). Hidden commands are generally useful to call back into pavilion
in generated scripts.

.. code::

    $ pav --help
    usage: pav.py [-h] [-v]
                  {run,show,status,view,results,result,log,clean,_run,set_status,status_set,wait,cancel}
                  ...

    Pavilion is a framework for running tests on supercomputers.

    positional arguments:
      {run,show,status,view,results,result,log,clean,_run,set_status,status_set,wait,cancel}
        run                 Setup and run a set of tests.
        show                Show pavilion plugin/config info.
        status              Get status of tests.
        view                Show the resolved config for a test.
        results (result)    Displays results from the given tests.
        log                 Displays log for the given test id.
        clean               Clean up Pavilion working diretory.
        set_status (status_set)
                            Set status of tests.
        wait                Wait for statuses of tests.
        cancel              Cancel a test, tests, or test series.

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Log all levels of messages to stderr.


_setup_arguments(self, parser)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Every Pavilion command plugin must provide a
**_setup_arguments(self, parser)** method. It will
get passed a python ``argparse`` parser that you can use to add arguments to
your command. This parser will already be configured to include the basics
of the command as specified when you called the parent's ``__init__`` method.

.. code:: python

    def _setup_arguments(self, parser):
        parser.add_argument(
            '-s', '--status', action='store_true', default=False,
            help='Prints status of cancelled jobs.'
        )
        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Prints status of cancelled jobs in json format.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to cancel. These may be any mix of '
                 'test IDs and series IDs. If no value is provided, the most '
                 'recent series submitted by the user is cancelled. '
        )
        # No need to return anything.

See the official documentation on
`argparse <https://docs.python.org/3.5/library/argparse.html>`__
for more information on defining arguements.


run(self, pav_cfg, args)
^^^^^^^^^^^^^^^^^^^^^^^^

The run command is what actually executes your command. Other than a few
Pavilion conventions you should follow, each command is free to do anything
it needs to.

Arguments
~~~~~~~~~

- It will be given a couple of useful parameters.

  - ``pav_cfg`` - The pavilion configuration object. A dictionary like
    object that contains all of the base pavilion configuration attributes,
    as well as useful things like the path to the general working
    directory. ``pav_cfg.working_dir``
  - The ``args`` object containing all of the pavilion command arguments. It
    will contain all the arguments specific to your command, as well
    as the general pavilion arguments (like --verbose).

Return Values
~~~~~~~~~~~~~

Pavilion's return value is the return value of whatever command was run. So
if your command succeeds, you should return ``0``. If your command fails,
you return an appropriate error code from the ``errno`` library.

.. code:: python3

    import errno
    from pavilion import utils

    class KnownRuns(commands.Command):
        ...

        def run(self, pav_cfg, args):
            """Print the number test runs in the working_dir."""

            runs_dir = pav_cfg.working_dir/'test_runs'
            try:
                runs = list(runs_dir.iterdir())
            except PermissionError as err:
                utils.fprint(
                    "Could not access run dir at {}: {}"
                    .format(str(runs_dir), err),
                    color=utils.YELLOW,
                    file=sys.stderr)

                return errno.EACCESS

            utils.fprint(len(runs))
            return 0

Exceptions
~~~~~~~~~~

Pavilion commands should **never** raise exceptions, or let the exceptions
of anything they call to go uncaught. Uncaught exceptions are always considered
to be a bug in Pavilion.

When dealing with non-Pavilion libraries, you'll have to work out how to
handle any exceptions they raise yourself. Each Pavilion library, however,
comes with one or more custom exceptions that should be the **only** exception
type raised by that library. These exceptions should contain information
about what went wrong, so you'll probably want to print that information for
the user like in the example above.

Output via ``utils.fprint()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Most command output should be given through either the ``utils.fprint``
function (or ``utils.draw_table``).

``utils.fprint`` is just like the standard python command, except that it
allows for ANSI color sequences through the ``color`` argument.

.. code:: python3

    from pavilion import utils

    utils.fprint("hello world", color=utils.YELLOW)

- The core output of your command should be given via stdout.

  - By default, output is meant for human readability, so colorization is
    encouraged.
- Error output should be

Color Scheme
^^^^^^^^^^^^

The ``utils`` module provides names that map to the standard ANSI 3/4 bit
foreground colors and a few special format codes. While fprint can take any
ANSI sequence as the color (including 8 and 24 bit color codes), only the basic
colors are typically mapped by user color schemes to ensure readability.

+------------+-------+-------------------------------+
+ Color      + Code  + Usage                         +
+============+=======+===============================+
+ BLACK      + 30    + Default                       +
+------------+-------+-------------------------------+
+ RED        + 31    + Use for fatal errors          +
+------------+-------+-------------------------------+
+ GREEN      + 32    + Use for 'success' messages    +
+------------+-------+-------------------------------+
+ YELLOW     + 33    + Non-Fatal Errors (Warnings)   +
+------------+-------+-------------------------------+
+ BLUE       + 34    + Discouraged (contrast issues) +
+------------+-------+-------------------------------+
+ CYAN       + 35    + Info messages                 +
+------------+-------+-------------------------------+
+ GREY/WHITE + 37    +                               +
+------------+-------+-------------------------------+
+ BOLD       + 1     +                               +
+------------+-------+-------------------------------+
+ FAINT      + 2     +                               +
+------------+-------+-------------------------------+
+ UNDERLINE  + 4     +                               +
+------------+-------+-------------------------------+

Output via ``utils.draw_table()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The utils ``draw_table()`` function provides an easy yet feature-rich way to
draw dynamic output tables to screen. The table's contents will be automatically
wrapped to the terminal size, the text can be colorized, and more.

.. code:: python3

    from pavilion import utils
    import sys

    # The table data is expected as a list of dictionaries with identical keys.
    # Not all dictionary fields will necessarily be used. Commands will
    # typically generate the rows dynamically...
    rows = [
        {'color': 'BLACK',  'code': 30, 'usage': 'Default'},
        {'color': 'RED',    'code': 31, 'usage': 'Fatal Errors'},
        {'color': 'GREEN',  'code': 32, 'usage': 'Warnings'},
        {'color': 'YELLOW', 'code': 33, 'usage': 'Discouraged'},
        {'color': 'BLUE',   'code': 34, 'usage': 'Info'}
    ]

    # The data columns to print (and their default column labels).
    columns = ['color', 'usage']

    utils.draw_table(
        outfile=sys.stdout,
        field_info={},
        fields=columns,
        rows=rows)


The ``run`` method should only take three arguments: self, pav\_cfg,
args. Pav\_cfg is the pavilion configuration file which holds all of the
information about pavilion, and args is the list of arguments given when
the command was run.

Args is the parsed argument object from argparse, and will contain all
your arguments as attributes ``args.myarg.`` For example, if you wanted
to get the list of tests provided when the command was run you would
reference the list by ``args.tests``. Note, for flags like ``-s`` you
get the name of the argument from the long name, i.e. ``--status``
specifies that ``args.status`` will hold the information required for
the status argument (in this case it will be a bool value).

When working with tests (I believe just about every command will be),
you need to remember that the arguments are strings. Because of this you
will need to import additional libraries, most importantly
``from pavilion.pav_test import TestRun``, to allow yourself the ability
to access the actual test object. If you anticipate using series as well
it will also be important to add ``from pavilion import series``. Below
is some sample code used to generate the lists of tests provided by
``args.tests`` including the ability to extract those in a test series.

.. code:: python

    for test_id in args.tests:
        if test_id.startswith('s'):
            test_list.extend(series.TestSeries.from_id(pav_cfg,int(test_id[1:])).tests)
        else:
            test_list.append(test_id)

This code will populate a list of all test IDs, but they are still
strings so you will need to do one of the following to get each test
object.

.. code:: python

    # Using Imported Series Module
    test_object_list, test_failed_list = series.test_obj_from_id(pav_cfg, test_list)

Note, when using ``series.test_obj_from_id`` error handling is handled
for you, as it will return a tuple made up of a list of test objects,
and a list of test IDs that couldn't be found. Because of this,
``series.test_obj_from_id`` is the preferred way of accessing test
objects.

Now that you have a test object you can get valuable information out of
it. A test object has quite a few attributes, here are some of the more
important ones:


You can access the most recent status object of the test by calling
``status = test.status.current()``. This also has a few attributes that
allow you to extract relevant status information, like:

+--------------------+-------------------------------------------------------------+
| Attribute          | Detail                                                      |
+====================+=============================================================+
| ``status.state``   | Returns the state of the test object.                       |
+--------------------+-------------------------------------------------------------+
| ``status.when``    | Returns the time stamp of this status object.               |
+--------------------+-------------------------------------------------------------+
| ``status.note``    | Returns any additional collected information on the test.   |
+--------------------+-------------------------------------------------------------+

An example of using the different attributes and methods can be seen
below, this is a simplified version of what is being done in the
pavilion cancel command.

.. code:: python

    test_object_list, test_failed_list = series.test_obj_from_id(pav_Cfg, test_list)
    for test in test_object_list:
        # Requires that the schedulers module be loaded
        scheduler = schedulers.get_scheduler_plugin(test.scheduler)
        status = test.status.current()
        if status.state != STATES.COMPLETE:
            sched.cancel_job(test)
