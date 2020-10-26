Scheduler Plugins
=================

Scheduler plugins take care of the scheduling part of testing. They provide
tests with a set of variables that can be used in the test, and handle passing
test runs off to the control of the scheduler.

Everything in :ref:`plugins.basics` applies here, so you should read that first.

This may seem quite daunting at first. The hard part, however, is typically
in parsing the information you get back from the scheduler itself. Interfacing
that with Pavilion is fairly easy.

**NOTE:** Pavilion 2.4 will be the *'scheduler'* update release. We're going to
be revamping how these work to some extent in that release. There are notes
below in the places this will matter. Conversions from <2.4 scheduler
plugins to 2.4+ plugins should be fairly trivial.

.. contents::

Scheduler Requirements
----------------------

For a scheduler to work with Pavilion, it must:

- Produce jobs with a unique (for the moment), trackable job id
- Produce jobs that can be cancelled
- Allow a job to be started asynchronously.

The Pavilion Scheduler plugin system was designed to be flexible
in order to support as many schedulers as possible.

Scheduler Plugins
-----------------

There are two parts to every scheduler plugin:

The Scheduler Plugin Itself
    This inherits from the 'pavilion.schedulers.SchedulerPlugin' class. They
    encompass:

    1. Provide a configuration section specific to your scheduler for the
       test yaml files.
    2. Gathering information about the system from the scheduler. (optional)
    3. Filtering the node list according to test parameters. (optional)
    4. Kicking off the test, typically by writing a kickoff script that
       runs on the allocation and runs `pav _run <test_id>` for a given
       test run.
    5. Providing a means to cancel test runs.
    6. Providing a means to get info on 'SCHEDULED' test runs.
    7. Provide a means for the scheduler to know if you're currently in an
       allocation.

    Implementing each of these steps involves overriding the corresponding
    method from the base SchedulerPlugin class.

Scheduler Variables
    This inherits from pavilion.schedulers.SchedulerVariables. It is meant
    to provide variables that tests can use in their configurations.

    They should provide:

    1. A 'run_cmd' variable that resolves to a command to run a script under
       the current allocation with parameters specified in the scheduler
       specific section of the test config. For 'slurm', this means
       an 'srun' command. For 'raw', it's an empty string.
    2. Lists of nodes (where applicable) for the machine as a whole and
       for the actual allocation.

In general, scheduler plugins:

1. Lazily evaluate - They should only ask the system once per invocation of
    the pav command for information from the underlying scheduler, and only
    when that scheduler is actually going to be used.
2. Don't know what each allocation is, until after it is made.

Future Bits to Keep in Mind:

1. While scheduler plugins only schedule one test run per allocatiion, we
   would like to allow for multiple test runs per allocation in the future.
   This will include cases where the allocation is not the exact size
   asked for by the test.

Writing a Scheduler Plugin Class
--------------------------------

A mentioned above, there are 6 basic things a scheduler must do. As such,
there are specific methods of the scheduler class to override for each of
those. You may have to add additional methods for handling data as it's
returned from the scheduler; it's not always easy to parse. Additionally,
Pavilion makes no assumptions about what that data looks like or how to
structure it once received.

Handling Errors
~~~~~~~~~~~~~~~

Your scheduler class should catch any errors it reasonably expects to occur.
This includes OSError when making system calls, ValueError when manipulating
values (like converting strings to ints), etc. When handling the exception,
record what went wrong along with the original message (in the exceptions
first argument (``exc.args[0]``), and raise a SchedulerPluginError with that
message.

.. code-block:: python

    from pavilion.schedulers import SchedulerPluginError

    try:
        int(foo)
    except ValueError as exc:
        raise SchedulerPluginError(
            "Invalid value for foo.\n - {}".format(exc.args[0]))

This allows Pavilion to catch and handle predictable errors, and pass them
directly to the user.

Init
~~~~

Scheduler plugins initialize much like other Pavilion plugins:

.. code-block:: python

    from pavilion import schedulers

    class Slurm(schedulers.SchedulerPlugin):

        def __init__(self):
            super().__init__(
                name='slurm',
                description='Schedules tests via the Slurm scheduler.'
            )

Most customization is through method overrides and a few class variables that
we'll cover later.


.. _Yaml Config: https://yaml-config.readthedocs.io/en/latest/

Configuraton
~~~~~~~~~~~~

Pavilion uses the `Yaml Config`_ library to manage it's configuration format.
Yaml Config uses 'config elements' to describe each component of the
configuration and their relationships. We'll be using a restricted set
of these to add a scheduler specific config section to the test config.

The ``get_conf()`` method should be overridden to return a list
of this configuration elements.

**NOTE** - In future updates much of this configuration will be unified.
Where possible, use the same key values as below. It's ok if those keys
don't accept the same values.

.. code-block:: python

    def get_conf(self):
        """Set up the Slurm configuration attributes."""

        return yc.KeyedElem(
            self.name,
            help_text="Configuration for the Slurm scheduler.",
            elements=[
                yc.StrElem(
                    'num_nodes', default="1",
                    help_text="Number of nodes requested for this test. "
                              "This can be a range (e.g. 12-24)."),
                yc.StrElem(
                    'tasks_per_node', default="1",
                    help_text="Number of tasks to run per node."),
                yc.StrElem(
                    'mem_per_node',
                    help_text="The minimum amount of memory required in GB. "
                              "This can be a range (e.g. 64-128)."),
                yc.StrElem(
                    'partition', default="standard",
                    help_text="The partition that the test should be run "
                              "on."),
                yc.StrElem(
                    'immediate', choices=['true', 'false', 'True', 'False'],
                    default='false',
                    help_text="Only consider nodes not currently running jobs"
                              "when determining job size. Will set the minimum"
                              "number of nodes "
                ),
                yc.StrElem(
                    'qos',
                    help_text="The QOS that this test should use."),
                yc.StrElem(
                    'account',
                    help_text="The account that this test should run under."),
                yc.StrElem(
                    'reservation',
                    help_text="The reservation this test should run under."),
                yc.StrElem(
                    'time_limit', regex=r'^(\d+-)?(\d+:)?\d+(:\d+)?$',
                    help_text="The time limit to specify for the slurm job in"
                              "the formats accepted by slurm "
                              "(<hours>:<minutes> is typical)"),
            ]
        )

There are some restrictions on configuration elements and features you can
use:

1. String values only - Non-structural elements (list, dict) should
    be limited to the StrElem type.
2. Manually Validate - We intend to include a system like that in
    result_parsers for config validation in a future release,
    but for now you must manually validate items as needed.

While the example above only uses StrElem, you can have KeyedElem (a
mapping that excepts only specific keys), ListElem,
or CategoryElem (a mapping that accepts generic keys) structures as well.

.. _plugins.scheduler.gather_data:

Gathering Scheduler Data
~~~~~~~~~~~~~~~~~~~~~~~~

At this point you have two options:

    1. Support ``num_nodes: 'all'``.
    2. Support only specific node counts or ranges.

It is highly recommended that you write your plugin to support 'all', but it
is not strictly required. As a side effect, it means you can also support
other dynamic node selection options for your scheduler.

Setting num_nodes to 'all' tells Pavilion to use all currently useable nodes
that also meet other restrictions such as the partition. Most schedulers (to
our knowledge) don't natively support this, however. Your plugin will have to
determine what 'all' means, given the state of the nodes on the system.

To do this, you will have to gather the state of all nodes on the system.
Most schedulers provide a means to do this; for slurm we do it through the
'scontrol' command which is fairly fast and efficient even for a large number
of nodes. It should be noted that such calls can be taxing on the scheduler
itself, which is part of why Pavilion 'lazily' evaluates these calls.

To gather data for your scheduler, override the ``_get_data()`` method, which
should return a dictionary of the information. The structure of this
dictionary is entirely up to you. How to gather that data is
scheduler dependent, and thus out the scope of this tutorial.

Filtering Node Data
~~~~~~~~~~~~~~~~~~~

If you chose to support 'num_nodes: all', you'll want to translate that
into an actual number of nodes for Pavilion to request. The scheduler plugin
base class provides a stub ``_filter_nodes()`` methods to accomplish this,
though the implementation of this filter is entirely scheduler dependent.

The Slurm plugin handles this into two steps:
 1. It filters nodes based on the config criteria, like 'partition'.
 2. It then uses that to calculate a 'node_range' string that can be
    handed to Slurm.

One needs to be very careful in the filtering of nodes and calculation of this
range. Mismatches between what nodes Pavilion thinks are usable and which
nodes your scheduler thinks are usable can and will cause Pavilion tests to
hang waiting on nodes that will never be allocated.

Lastly, it should be noted that the Slurm plugin provides an 'immediate'
configuration flag. This changes the base criteria for node availability from
'allocatable' to 'not currently allocated'. This is useful for tests that
just need some nodes now, rather than a strict amount.

Kicking Off Tests
~~~~~~~~~~~~~~~~~

You must provide a means for Pavilion to use your scheduler to 'kick off'
tests, because that's kind of the point of all of this. The built-in
mechanisms for doing this involve generating a shell script that will be
handed to the scheduler and run on an allocation.

The scheduler plugin base class already generates this script through
``_create_kickoff_script()`` method, all you have to do get your scheduler
to run that script on an allocation appropriate given the test's requested
scheduling parameters. For many schedulers, the heading of these scripts
define the parameters for the job. For others, the parameters must be passed
on the command line or through environment variables. We cover how to do all
of these things below.

You can, alternatively, not use the predefined kickoff script at all. In that
case you must do the following to properly run a test in an allocation:

1. The ``PATH`` environment variable on the allocation must include
   the Pavilion bin directory (``pav_cfg.pav_root/'bin'``).
2. The ``PAV_CONFIG_FILE`` environment variable must be set to
   the path to the Pavilion config (``pav_cfg.pav_cfg_file``). *This is not
   to be confused with the ``PAV_CONFIG_DIR`` environment variable.*
3. You must then run the test on the allocation with ``pav _run <test_id>``.
4. All output from the kickoff script should be redirected to the test's
   'kickoff' log (``test_obj.path/'kickoff.log'``)

Kicking off with a 'batch' script.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Most 'batch' scripts begin with a 'header' of scheduling parameters, followed
by a shell script. In our case, the shell script is already generated for us,
we simply need to define the header information. The composition of the
kickoff script is handled by the Pavilion 'ScriptComposer' class, which happens
to take a 'ScriptHeader' instance as an argument. We simply need to define a
custom 'ScriptHeader' class, and override the ``_get_kickoff_script_header()``
method to return that instead of the default.

By default the auto-generated kickoff script will have a '.sh' extension. You
can change that by setting the ``KICKOFF_SCRIPT_EXT`` class variable on your
scheduler plugin.

Here is an annoted excerpt from the Slurm scheduler plugin that demonstrates
this:

.. code-block:: python

    from pavilion import scriptcomposer

    class SbatchHeader(scriptcomposer.ScriptHeader):
        """Provides header information specific to Slurm sbatch files."""

        # Your init can take any arguments; we'll customize how it's called.
        def __init__(self, sched_config, nodes, test_id, slurm_vars):
            super().__init__()

            # In this case, we'll use the whole scheduler config section
            # from the test.
            self._conf = sched_config

            # We also take the preformatted value for '--nodes' directive.
            self._nodes

            # We use the test id to name the job
            self._test_id = test_id

            # We also use the 'sched' vars, as they already format some
            # of the information we need in a slurm compatible way.
            self._vars = slurm_vars

        # This method simply returns a list of lines that will be placed
        # at the top of our script.
        def get_lines(self):
            """Get the sbatch header lines."""

            lines = super().get_lines()

            # Here we just add directives in the slurm sbatch format,
            # according to the test's configuration.
            lines.append(
                '#SBATCH --job-name "pav test #{s._test_id}"'
                .format(s=self))
            lines.append('#SBATCH -p {s._conf[partition]}'.format(s=self))
            if self._conf.get('reservation') is not None:
                lines.append('#SBATCH --reservation {s._conf[reservation]}'
                             .format(s=self))
            if self._conf.get('qos') is not None:
                lines.append('#SBATCH --qos {s._conf[qos]}'.format(s=self))
            if self._conf.get('account') is not None:
                lines.append('#SBATCH --account {s._conf[account]}'.format(s=self))

You'll also need to override the ``_get_kickoff_script_header()`` method of
your scheduler plugin to return an instance of your custom header class for use
in the kickoff script.

.. code-block:: python

    def _get_kickoff_script_header(self, test):
        """Get the kickoff header. Most of the work here """

        sched_config = test.config[self.name]

        # For the slurm scheduler, we store our node info under 'nodes'.
        nodes = self.get_data()['nodes']

        return SbatchHeader(sched_config,
                            # This is where we handle our node filtering and
                            # get a pre-formatted node range.
                            self._get_node_range(sched_config, nodes.values()),
                            test.id,
                            self.get_vars(test))


Scheduling a Test
~~~~~~~~~~~~~~~~~

The ``_schedule()`` method of your scheduler class is responsible for handing
control of each test run to the scheduler and returning a job id for that run.

Typically this involves running one or more shell commands to tell your
scheduler to enqueue a command or script. This is typically done with the
``subprocess`` module. Since Pavilion support Python 3.5+, you can use the
new(ish) ``subprocess.run()`` function, though ``subprocess.Popen()`` may be
more appropriate.


Composing Commands
^^^^^^^^^^^^^^^^^^

You should compose your commands as a list. (Try to avoid the
'shell=True' string based method. It tends to be error prone). Full paths
to commands can be found with the distutils module.

.. code-block:: python

    import distutils.spawn

    srun = distutils.spawn.find_executable('srun')
    if srun is None:
        raise SchedulerError

    my_cmd = [srun]

    # Building your commands with a list is simple and flexible.
    if redirect_output:
        my_cmd.extend(['-o', outfile])

    mycmd.append('--partition=strange')

    subprocess.run(my_cmd)

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

