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

1. A 'kickoff' method - a means to acquire an allocation given the scheduler parameters
   and run a script on it. Also needs to return a 'serializable' job id, to uniquely
   identify a scheduler job.
2. A 'job_status' method, that asks the scheduler whether a given job id is
   scheduled, had a scheduling error, was cancelled, or is running.
3. A 'cancel' method, to cancel a given job id.
4. A '_get_alloc_nodes' method, to get the list of nodes in an allocation that
   Pavilion is currently running under.

Advanced schedulers must also override the following. They are fully documented
in the 'pavilion.schedulers.advanced.SchedulerPluginAdvanced' class.

1. '_get_raw_node_data' - Should fetch and return a list of information about each node.
    This is the per-node information mentioned above.
2. '_transform_row_node data' - Converts that data into a '{node: info_dict}' dictionary.
   There are several required keys each node's info_dict must contain, see the method
   documentation for info on the required and optional keys.

Scheduler Variables
~~~~~~~~~~~~~~~~~~~

Every scheduler should also include a scheduler variables class, assigned to your
class's 'VAR_CLASS' class variable. This provides information from the scheduler
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
we'll cover later.  There is also a `SchedulerPluginBasic` which allows for working
with schedulers with a much reduced feature set.


.. _Yaml Config: https://yaml-config.readthedocs.io/en/latest/

Configuraton
~~~~~~~~~~~~

Pavilion has unified scheduler plugin configuration into the `schedule` section. Not all keys from
this section will apply to your scheduler, and that's ok. Most keys are handled automatically given
the information gathered on nodes.

You can also, optionally, add a scheduler specific configuration section. To do this, you'll need
to override the `_get_config_elems()` method. This method returns three items:

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
    range checking. These can take several forms, see the `SchedulerPlugin._get_config_elems()`
    method documentation.
  - Don't use the built-in validation and default options for the yaml_config objects,
    use the validation callbacks/objects and defaults dictionary returned by the function
    instead.

Kicking Off Tests
~~~~~~~~~~~~~~~~~

Pavilion scheduler plugins generate a kickoff script for each job - a script that will
be handed to the scheduler to be run within the allocation. That script will run Pavilion
one or more times within that allocation, starting a `run.sh` script for each test. It's
the responsibility of the `run.sh` script to actually run applications under MPI, either
with `mpirun`, `srun`, or similar.

Many schedulers rely on a header information in that `kickoff` script to relay to
the scheduler what the settings for the allocation should be. This is header is optional - the
default header adds nothing to the file except a `#!/bin/bash` line. If you need to
define header lines, you'll need to create a class that inherits from
`pavilion.schedulers.scheduler.KickoffScriptHeader`, and override the
`_kickoff_lines` method. This method simply returns a list of header lines
to add.

Alternatively, when writing your `_kickoff` method, you can simply pass any relevant
information about the job to the scheduler directly through the command line
or API calls.

Either way, there are a set of parameters that must be passed on to the scheduler. These
are described in the `SchedulerPlugin` docstring. For those parameters that are unsupported
by


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

Regardless of how you kickoff a test, you must capture a 'job id' for it.

- It must be a string.
- It can otherwise be of any format. Only your scheduler plugin will need
  to understand that format.
- You may want to consider including host/system information in the id,
  so your plugin can know when it's running in a place that can actually
  reference that id. For instance, the raw scheduler starts a local process,
  but can't very well check the status of a process from a different machine.

An Example
^^^^^^^^^^

.. code-block:: python

    def _schedule(self, test, kickoff_path):
        """Submit the kick off script using sbatch.

        :param TestRun test: The TestRun we're kicking off.
        :param Path kickoff_path: The kickoff script path.
        :returns: The job id under this scheduler.
        """

        # We're going to save the slurm log in the test run directory, so it
        # isn't put just anywhere.
        slurm_out = test.path/'slurm.log'

        # Run the command to scheduler our batch script.
        # The default scripts use 'exec >' redirection to redirect all output
        # script to the kickoff log.
        # This should be a command that returns when our kickoff script is
        # in the scheduler queue.
        proc = subprocess.Popen(['sbatch',
                                 '--output={}'.format(slurm_out),
                                 kickoff_path.as_posix()],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        # Slurm prints the job id when starting an sbatch script, which we
        # capture and extract.
        stdout, stderr = proc.communicate()

        # Raise an error if the kickoff was a failure.
        if proc.poll() != 0:
            raise SchedulerPluginError(
                "Sbatch failed for kickoff script '{}': {}"
                .format(kickoff_path, stderr.decode('utf8'))
            )

        # Parse out the job id and return it. It will get attached to the
        # test run object and tracked that way.
        return stdout.decode('UTF-8').strip().split()[-1]

Cancelling Runs
~~~~~~~~~~~~~~~

To handle cancelling jobs, we'll be overriding the ``_cancel_job()``
method of your scheduler class.

You'll need to do the following:

1. (Typically) Compose and run a command to cancel the job given the
   job id you recorded.
2. (If cancelling is successful) set 'test.set_run_complete()' to
   mark the test as complete.
3. Set the test status to 'STATES.SCHED_CANCELLED'.
4. Return a ``StatusInfo`` object with the new status of the test, and
   a reasonable status message.

Additionally, there are four basic cases that need to be handled:

1. The job was never started. This is handled for you in ``cancel_job()``,
   which calls ``_cancel_job()``.
2. The job is enqueued but not yet running (or somewhere in between).
3. The job is running.
4. The job has finished.

Most of the time, this simply means you will try to cancel the job id
and capture any errors.

Additionally, if your job id encodes information that could denote that
the job can't be cancelled from the current machine, this is the place to
use it.

StatusInfo
^^^^^^^^^^

You shouldn't have to create a StatusInfo object (they come from
``pavilion.status_file``), just return the one returned when you set the
test status.

Example
^^^^^^^

Here's the (annotated) ``_cancel_job()`` from the slurm plugin.

.. code-block:: python

    def _cancel_job(self, test):
        """Scancel the job attached to the given test.

        :param pavilion.test_run.TestRun test: The test to cancel.
        :returns: A statusInfo object with the latest scheduler state.
        :rtype: StatusInfo
        """

        # In this case we simply need call scancel with our simple job id.
        cmd = ['scancel', test.job_id]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if proc.poll() == 0:
            # Scancel successful, pass the stdout message

            # Someday I'll add a method to do this in one shot.
            test.set_run_complete()
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Slurm jobid {} canceled via slurm.".format(test.job_id)

            )
        else:
            # We failed to cancel the test, let the user know why.
            return test.status.set(
                STATES.SCHED_CANCELLED,
                "Tried (but failed) to cancel job: {}".format(stderr))


Checking Test Run Status
~~~~~~~~~~~~~~~~~~~~~~~~

You'll need to override your scheduler's ``job_status()`` method. This method
is only used within a small window of a test's existence - when it has the
'SCHEDULED' state. This is set (for you) after your ``_schedule()`` method
is called, and is replaced by other states as soon as the test starts
running on the allocation.

Like ``_cancel_job()``, ``job_status()`` should return a StatusInfo object.
Unlike ``_cancel_job()`` you **should not set the test status**. This
prevents the test from receiving status updates every time you check it's
status.

**There is one exception to this.** If you find that the test run was cancelled
outside of Pavilion, do set the status to STATES.SCHED_CANCELLED and mark
the test as complete using ``test.set_run_complete()``. This
will prevent further calls to the scheduler regarding the status of this
cancelled test, and let Pavilion know the run is done.

For an example, refer to the ``job_status()`` method for the Slurm scheduler
plugin. As you'll see, this can be quite complex, and will depend greatly on
your scheduler.

Scheduler Availability
~~~~~~~~~~~~~~~~~~~~~~

The final method to override is ``available()``. This method returns
a bool denoting whether or not tests can be started with the given scheduler
on the current machine. It lets Pavilion quickly determine if it should bother
trying to start tests under this scheduler, and report errors to the user.

You don't need to do anything fancy here, simply figuring out if the basic
commands for your scheduler are installed is enough and using one to gather
basic system info is enough.

As mentioned above, ``distutils.spawn.find_executable()`` is useful here.

.. code-block:: python

    def available(self):
        """Looks for several slurm commands, and tests slurm can talk to the
        slurm db."""

        for command in 'scontrol', 'sbatch', 'sinfo':
            if distutils.spawn.find_executable(command) is None:
                return False

        # Try to get basic system info from sinfo. Should return not-zero
        # on failure.
        ret = subprocess.call(
            ['sinfo'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return ret == 0

.. _decoratored: https://www.programiz.com/python-programming/decorator

Scheduler Variables
-------------------

The second part of creating a scheduler plugin is adding a set of variables that
test configs can use to manipulate their test. Many of these will be
:ref:`deferred <tests.variables.deferred>` (they're only available
after the test is running on an allocation).

Pavilion provides a framework for creating these variables, the
``pavilion.schedulers.SchedulerVariables`` class. By inheriting from this
class, you can define scheduler variables simply by adding `decoratored`_
methods to your child class. The decorators do most of the hard work, you
simply have create and return the value.

Useful Attributes
~~~~~~~~~~~~~~~~~

You'll automatically get a number of useful things for creating variables
values.

1. The test run's scheduler config, via ``self.sched_config``.
2. The scheduler object itself, via ``self.sched``.
3. The scheduler's general data, via ``self.sched_data``.

   - This is the data generated in the :ref:`plugins.scheduler.gather_data`
     step.

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

Variable Name Conventions
~~~~~~~~~~~~~~~~~~~~~~~~~

When naming your variables, keep in mind the following conventions:

(no_prefix)
    ``node_list``, ``nodes``, etc.

    These variables apply to the whole cluster or the cluster head node.
    **They should never be deferred.**

alloc_*
    ``alloc_node_list``, ``alloc_max_mem``, etc.

    These variables apply to the whole allocation that a particular test
    run is running on. **They are always deferred.**

test_*
    ``test_node_list``, ``test_procs``, etc.

    These variables apply to the specific test run on a given allocation. At
    the moment, there should be no difference between these and 'alloc\_'
    variables. In the future, however, tests may be allocated on shared
    allocations larger than what the test specifically requested or needs.

test_cmd
    This variable should use other 'test\_' variables to compose a command that
    starts an MPI process within your allocation. It should restrict the
    test to just the number of processors/nodes requested by the test.
    Common examples are 'mpirun' or 'srun'.

Return Types
~~~~~~~~~~~~

Values returned should be:

1. A string
2. A list of strings.
3. A dict (with string keys and values)
4. A list of such dicts.

They cannot be more complex this this.

You can actually return non-string values; they will be converted to strings
automatically and recursively through the returned data structure.

Adding Variables
~~~~~~~~~~~~~~~~

Here's an annotated example, from the Slurm scheduler plugin, to walk you
through defining your own scheduler variable class.

.. code-block:: python

    import os
    from pavilion.schedulers import (
        SchedulerVariables, var_method, dfr_var_method)

    class SlurmVars(SchedulerVariables):

        # Methods that use the 'var_method' decorator are 'non-deferred'
        # variables.
        @var_method
        def nodes(self):
            """Number of nodes on the system."""

            # Slurm's scheduler data includes a dictionary of nodes.
            return len(self.sched_data['nodes'])

        @var_method
        def node_list(self):
            """List of nodes on the system."""

            return list(self.sched_data['nodes'].keys())

        @var_method
        def node_avail_list(self):
            """List of nodes who are in an a state that is considered available.
        Warning: Tests that use this will fail to start if no nodes are available."""

            # The slurm plugin allows you to define what node states are
            # considered 'available'. Actual node states are normalized to
            # make this work.
            avail_states = self.sched_config['avail_states']

            nodes = []
            for node, node_info in self.sched_data['nodes'].items():
                if 'Partitions' not in node_info:
                    # Skip nodes that aren't in any partition.
                    continue

                for state in node_info['State']:
                    if state not in avail_states:
                        break
                else:
                    nodes.append(node)

            return nodes

        # Methods that use the 'dfr_var_method' decorated are deferred.
        @dfr_var_method
        def alloc_nodes(self):
            """The number of nodes in this allocation."""
            # Since this is deferred, this will be gathered on the allocation.
            return os.getenv('SLURM_NNODES')

        @dfr_var_method
        def test_cmd(self):
            """Construct a cmd to run a process under this scheduler, with the
            criteria specified by this test.
            """

            cmd = ['srun',
                   '-N', self.test_nodes(),
                   '-n', self.test_procs()]

            return ' '.join(cmd)

