Scheduler Plugins
=================

Scheduler plugins take care of the scheduling part of testing. They provide
tests with a set of variables that can be used in the test, and handle passing
test runs off to the control of the scheduler.

Everything in :ref:`plugins.basics` applies here, so you should read that first.

This may seem quite daunting at first. The hard part, however, is typically
in parsing the information you get back from the scheduler itself. Interfacing
that with Pavilion is fairly easy.

.. contents::

Scheduler Requirements
----------------------

For a scheduler to work with Pavilion, it must:

- Produce jobs with a unique (for the moment), trackable job id
- Produce jobs that can be cancelled
- Allow a job to be started asynchronously.

The Pavilion Scheduler plugin system was designed to be flexible
in order to support as many schedulers as possible.

Pavilion also provides an advanced scheduler class that provides quite a few features:

- Allows tests to auto-size relative to available/up nodes.
- Will automatically break the system into discrete 'chunks' of nodes, allowing for
  tests that run over the whole system in a piecemeal fashion.

Advanced schedulers must be able to get an accurate inventory of nodes, including:

- Whether each node is currently 'up' or 'allocated'.
- System information about each node (CPUS, memory info, etc...)
- The scheduler 'groups' that the node belongs to: reservations, partitions. Pavilion's
  must be able to filter nodes according the allocation parameters the same way the scheduler would.

Advanced schedulers must also be able to dictate to the scheduler exactly which nodes to use.

Scheduler Plugins
-----------------

The Scheduler Plugin
~~~~~~~~~~~~~~~~~~~~

This inherits from the 'pavilion.schedulers.BasicSchedulerPlugin' or
'pavilion.schedulers.AdvancedSchedulerPlugin' class.  All of these are fully documented in
the 'pavilion.schedulers.scheduler.SchedulerPlugin' class.

All scheduler plugin require that you extend the base class by providing:

1. A ``_kickoff()`` method - a means to acquire an allocation given the scheduler parameters
   and run a script on it. Also needs to return a 'serializable' job id, to uniquely
   identify a scheduler job.
2. A ``job_status()`` method, that asks the scheduler whether a given job id is
   scheduled, had a scheduling error, was cancelled, or is running.
3. A ``cancel()`` method, to cancel a given job id.
4. A ``_get_alloc_nodes()`` method, to get the list of nodes in an allocation that
   Pavilion is currently running under.
5. An ``available()`` method, to tell Pavilion if your scheduler can be used at all.


Advanced schedulers must also override the following. They are fully documented
in the 'pavilion.schedulers.advanced.SchedulerPluginAdvanced' class.

1. ``_get_raw_node_data()`` - Should fetch and return a list of information about each node.
    This is the per-node information mentioned above.
2. ``_transform_raw_node_data()`` - Converts that data into a '{node: info_dict}' dictionary.

   There are several required keys each node's info_dict must contain, see the method
   documentation for info on the required and optional keys.

Basic scheduler plugins don't require any extra methods, but are limited in functionality.
See :ref:`tests.scheduling.types` for more info.

Scheduler Variables
~~~~~~~~~~~~~~~~~~~

Every scheduler should also include a scheduler variables class, assigned to your
class's 'VAR_CLASS' class variable. This provides information from the scheduler
for each test to use in it's configuration, such as ``sched.test_nodes`` (the
for each test to use in it's configuration, such as `sched.test_nodes` (the
number of nodes in the test's allocation). The base class uses information given
by the scheduler plugin and the test's configuration to figure out 99% of these
on its own. You'll only need to override a few.

Writing a Scheduler Plugin Class
--------------------------------

Handling Errors
~~~~~~~~~~~~~~~

Your scheduler class should catch any errors it reasonably expects to occur.
This includes OSError when making system calls, ValueError when manipulating
values (like converting strings to ints), etc. Once caught, then raise a Pavilion
specific error, in this case it should always be SchedulerPluginError. Pavilion exceptions
take a message about the local context as their first argument, and the prior exception
as the second (optional) argument.


.. code-block:: python

    from pavilion.schedulers import SchedulerPluginError

    try:
        int(foo)
    except ValueError as exc:
        raise SchedulerPluginError("Invalid value for foo.", exc)

This allows Pavilion to catch and handle predictable errors, and pass them
directly to the user.

Init
~~~~

Scheduler plugins initialize much like other Pavilion plugins:

.. code-block:: python

    from pavilion import schedulers

    class Slurm(schedulers.SchedulerPluginAdvanced):

        def __init__(self):
            super().__init__(
                name='slurm',
                description='Schedules tests via the Slurm scheduler.'
            )

Most customization is through method overrides and a few class variables that
we'll cover later.  There is also a ``SchedulerPluginBasic`` which allows for working
with schedulers with a much reduced feature set.


.. _Yaml Config: https://yaml-config.readthedocs.io/en/latest/

Configuraton
~~~~~~~~~~~~

Pavilion has unified scheduler plugin configuration into the 'schedule' section. Not all keys from
this section will apply to your scheduler, and that's ok. Most keys are handled automatically given
the information gathered on nodes.

You can also, optionally, add a scheduler specific configuration section. To do this, you'll need
to override the ``_get_config_elems()`` method. This method returns three items:

  1. A list of YamlConfig Elements.
  2. A dictionary of validation/normalization functions. These will be called to
     transform the data for each key to a standard format.
  3. A dictionary of default values for each key.

Pavilion uses the `Yaml Config`_ library to manage it's configuration format.
Yaml Config uses 'config elements' to describe each component of the
configuration and their relationships.

The Slurm scheduler plugin provides a solid example of this, but in general:

  - You should only use yaml_config StrElem, ListElem, KeyedElem (a dict with specific key
    and value formats), and CategoryElem (a dict with mostly unlimited keys, and a shared
    value format).
  - Validators for individual keys are optional, but you should do str to int conversion and value
    range checking. These can take several forms, see the ``SchedulerPlugin._get_config_elems()``
    method documentation.
  - Don't use the built-in validation and default options for the yaml_config objects,
    use the validation callbacks/objects and defaults dictionary returned by the function
    instead.

Kicking Off Tests
~~~~~~~~~~~~~~~~~

Pavilion scheduler plugins generate a kickoff script for each job - a script that will
be handed to the scheduler to be run within the allocation. That script will run Pavilion
one or more times within that allocation, starting a ``run.sh`` script for each test. It's
the responsibility of the ``run.sh`` script to actually run applications under MPI, either
with ``mpirun``, ``srun``, or similar.

Many schedulers rely on a header information in that ``kickoff`` script to relay to
the scheduler what the settings for the allocation should be. This is header is optional - the
default header adds nothing to the file except a ``#!/bin/bash`` line. If you need to
define header lines, you'll need to create a class that inherits from
``pavilion.schedulers.scheduler.KickoffScriptHeader``, and override the
``_kickoff_lines()`` method. This method simply returns a list of header lines
to add.

Alternatively, when writing your ``_kickoff`` method, you can simply pass any relevant
information about the job to the scheduler directly through the command line
or API calls.

Either way, there are a set of parameters that must be passed on to the scheduler. These
are described in the ``SchedulerPlugin._kickoff`` docstring. You can safely ignore parameters
that aren't supported by your scheduler.


Composing Commands
~~~~~~~~~~~~~~~~~~

Your scheduler plugin will most likely require that you run commands in a subshell. This
section provides guidance on how to do so reliably under Pavilion.

.. code-block:: python

    # These should be at the top of the file, as standard
    import subprocess
    import shutil

    # Use shutil.which to find the path to your executable, if needed
    srun_cmd = shutil.which('srun')
    if srun_cmd is None:
        raise SchedulerError("Could not find srun command path.")

    my_cmd = [srun_cmd]

    # Building your commands with a list is simple and flexible.
    if config['account']:
        my_cmd.extend(['-A', config['account']])

    # subprocess.check_output will run your command to completion and simultaniously redirect
    # and gather the output.
    try:
        # You should also redirect stderr, as is appropriate for your command.
        run_output = subprocess.check_output(my_cmd, stderr=subprocess.STDOUT)
    # A CalledProcessError will be raised if the command returns an error code.
    except CalledProcessError as err:
        raise SchedulerError("Error calling srun. Return code '{}', msg:\n{}"
                             .format(err.returncode, err.output)

    # The output will be binary, and will need to be decoded
    run_output = run_output.decode()


To find commands on a system, 'distutils.spawn.find_executable' is essentially
an in-python version of 'which'.

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

You can also add to the environment through the ``env`` argument, though you
need to make sure to include the base environment in most cases.

.. code-block:: python

    import os
    import subprocess

    myenv = dict(os.environ)
    myenv['MY_ENV_VAR'] = 'Hiya!'
    myenv['PATH'] = '{}:/opt/share/something/bin'.format(os.environ['PATH'])

    subprocess.run(my_cmd, env=myenv)

Job Id's
^^^^^^^^

Regardless of how you kickoff a test, you must capture a job id for it, and return it
as part of a JobInfo object (which is really just a dict). All scheduler commands that act on a
job, like cancel, will have access to this object either directly or through an attached test.

The JobInfo dict can contain any keys and values you like, as long as they're all strings. It's
useful to include the 'sys_name' of the machine you're on (via 'sys_vars.get_vars(True)
["sys_name"]') so that you also check if the system that started the job is the same as the one
that's manipulating it.

Job Status
~~~~~~~~~~

The '_job_status()' method takes the Pavilion base config (Pavilion's configuration, rather than
a test configuration), and the JobInfo for job that status is needed for. It returns a
'TestStatusInfo' object, describing the job state returned by the scheduler.

It's job is to translate all the complicated potential job states for any particular scheduler
into one of four more basic states understood by Pavilion:

- SCHED_ERROR - There was an error in scheduling the job
- SCHED_CANCELLED - The job was cancelled (usually externally to Pavilion)
- SCHED_RUNNING - The job is running (but not necessarily the particular test.
- SCHEDULED - The job is simply waiting for an allocation.

Note that this will only be called if the cached job status in the plugin's internal
'_job_statuses' dictionary is out of date. In fact, you can (as the slurm plugin does), simply
use the first call of this function to update the status of all the jobs on the system at once
in that dictionary.

.. code-block:: python

    # The STATES object has attributes for each valid Pavilion test state,
    # but you'll only be using those with the 'SCHED_' prefix.
    from pavilion.status_file import STATES
    from pavilion.status_file import TestStatusInfo

    my_status = TestStatusInfo(
        STATES.SCHED_ERROR,     # Simply pass one of the valid scheduler state constants.
        "Cthulhu at my test.")  # Along with a longer message describing the state.

Cancelling Runs
~~~~~~~~~~~~~~~

To write the 'cancel()' method, all you need to do is use the job id you saved when you
kicked a test off. If there's an error doing so, return a message why, otherwise simply
return 'None' to denote success.

All the more complicated parts of cancelling are handled by functions that will wrap your method,
so there really isn't too much to worry about here.  The Slurm plugin cancel command is a good
example in how simple this can be.

Finding the Allocation Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``_get_alloc_nodes()`` method needs to be overridden to find the list of nodes for
a test's allocation. This will always be called only from within the allocation - typically
the scheduler sets an environment variable with this information.

Note that this may not always be called. If chunking is used, the scheduler plugin will know
the exact list of allocation nodes before the test is kicked off.


Scheduler Availability
~~~~~~~~~~~~~~~~~~~~~~

The 'available()' method simply tells Pavilion if the scheduler is available to run jobs
on the given system. It's not a measure of operability, simply a True/False value saying
whether the basic commands (or API modules) needed to use the plugin exist.

.. _decoratored: https://www.programiz.com/python-programming/decorator

Advanced Scheduler Methods
--------------------------

If you're trying to write an advanced scheduler plugin using the 'SchedulerPluginAdvanced'
parent class, there are a couple more methods to override.  These are:

- ``_get_raw_node_data()`` - A method to gather raw information on the cluster's nodes.
- ``_transform_raw_node_data`` - A method that translates that same data into a dictionary of
  information about each node.

For information on overriding each of these, refer to the doc strings for each as defined
in the 'pavilion.schedulers.advanced.SchedulerPluginAdvanced' class. They will tell you
everything you need to know about how to write those methods.

The purpose of these methods is to provide Pavilion with the information it needs to make
decisions about what nodes to schedule on itself, rather than relying on the scheduler to do
so. This allows Pavilion to partition the system in ways that the scheduler might not support
on its own. These include the ability to specify 'all' as the number of nodes requested,
and the ability to perform :ref:`tests.scheduling.chunking` of system into multiple, evenly sized
pieces.

The downside is that the per-node information must be perfectly accurate or jobs may be rejected by
the scheduler (such as when improperly requesting nodes not in the selected partition) or simply
wait in the queue forever (such as when selecting nodes that are down).

Scheduler Variables
-------------------

The second part of creating a scheduler plugin is adding a set of variables that
test configs can use to manipulate their test. The vast majority of these are automatically
derived from the information you gathered about the nodes for Advanced scheduler plugins or
via the ``schedule.cluster_info`` test configuration information for Basic scheduler plugins.

Pavilion provides a framework for creating these variables, the
``pavilion.schedulers.vars.SchedulerVariables`` class. By inheriting from this
class, you can define scheduler variables simply by adding `decoratored`_
methods to your child class. The decorators do most of the hard work, you
simply have create and return the value. The class itself provides good documentation
on how to do this.

The most important variable in all of these is the ``test_cmd`` variable, which is probably the
only variable that will need to be customized for your scheduler plugin. It provides
tests with an mpi startup command, such as ``mpirun``, with arguments automatically set
according to the test's settings. Pavilion tests generally use this variable to prefix
their mpi runs when writing their run scripts:

.. code-block:: yaml

    test_cmd_example:

      scheduler: slurm
      schedule:
        nodes: 32

      run:
        cmds:
          - '{{test_cmd}} ./my_mpi_cmd'

How to write a ``test_cmd`` variable is documented in the ``SchedulerVariables.test_cmd()`` method's
doc string.


Adding the Scheduler Vars to the Scheduler Plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To add your scheduler variable class to your scheduler plugin, simply
set the variable class as the ``VAR_CLASS`` attribute on your scheduler.

.. code-block:: python

    from pavilion import schedulers

    class MyVarClass(schedulers.SchedulerVariables):
        # Your scheduler variable class

    class MySchedPlugin(schedulers.SchedulerPlugin):
        VAR_CLASS = MyVarClass

