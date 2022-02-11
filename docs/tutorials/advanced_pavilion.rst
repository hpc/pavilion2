.. _tutorials.advanced:

Tutorial: Advanced Pavilion
===========================

This tutorial assumes you already understand the basics of using Pavilion, and have it set up
for the tutorials. That's already covered here: :ref:`tutorial.basic`.

This tutorial will teach you:

- How to make your tests generic, and able to run on most machines.
- How to run under a real scheduler.
- How to make tests only run in certain situations.
- How to make tests self-multiply.
- And more!  Probably.

Unlike the basic tutorial, some parts of this tutorial require an actual cluster. We've
tried to keep those parts to a minimum.

.. contents:: Table of Contents

Starting Point
--------------

This tutorial starts where the last left off, with a test configuration
in ``examples/tutorials/tests/tutorial.yaml`` that looked something like this:

.. code-block:: yaml

    basic:
        build:
            source_path: hello_world.c

            # We're about to use gcc to compile the test. If you need to
            # load a module to get gcc, add that module to this list.
            modules: []

            cmds:
                - gcc -o hello hello_world.c

        run:
            cmds:
                - './hello Paul'

        result_parse:
          regex:
            result:
              regex: '^Hello .*!$'
              action: store_true

          split:
            "_, lucky":
              sep: ':'
              for_lines_matching: '^Today'
              match_select: first

        result_evaluate:
          normalized_luck: 'round(lucky * 1000)'

Feel free to cut and paste this, but it's recommended to manually type in
everything else we tell you to do in this tutorial.


Variables and Expressions
-------------------------

Our hello world test config works, but it's pretty specific. It says hello to you, but
it would be really nice if it said hello to whoever ran it.

Pavilion comes with a wide variety of variables you can use to make your tests more generic, and
you can also provide your own via the test config and through plugins. Variables can be inserted
into just about any string value in a Pavilion test config using double curly braces:
``'{{variable name}}'``.

User provided variables are given in the 'variables' section of each test config. They have a
fairly limited set of forms. They can be:

Change the test config to look like this:

.. code-block:: yaml

    basic:

    # ...

    variables:
        myuser: bob

    run:
        cmds:
            # We insert the user into our test.
            - './hello {{myuser}}'

    # ...

Run this test, and look at the generated run script (``pav cat <test_id> run.sh``), you'll
see that the variable was replaced in the config _BEFORE_ the run script was written.

Variable Format
~~~~~~~~~~~~~~~

Variables in Pavilion can also be lists and dictionaries, but in a fairly limited way. Here's an
example of all valid variable formats, and how to use them.

.. code-block:: yaml

    variable-formats:

        variables:
            single_value: "hello"

            # A variable can be a list of values.
            multi_value:
                - "thing1"
                - "thing2"

            # A variable can be a single dictionary/mapping.
            structured_value:
                name: "Bob"
                moniker: "bobzilla"
                uid: "2341"

            # Or a list of mappings, as long as they have the same keys.
            more_structured_values:
                - name: Paul
                  moniker: "paulblematic"
                - name: Nick
                  moniker: "nickelback"
                - name: Francine
                  moniker: "frantastic"

        run:
            cmds:
                # You can use most variables just about anywhere in the test config,
                # not just here.

                # As seen in the prior example.
                - 'echo {{single_value}}'

                # You can access individual list items like this, counting from 0.
                - 'echo "{{multi_value.0}} {{multi_value.1}}"
                # If you want the first item, the index is optional.
                - 'echo "{{multi_value}}"

                # For structured values, you have to specify a sub-key
                - 'echo "My name is {{structured_value.name}}"'
                - 'echo "Your name is {{more_structured_values.1.name}}"'

The above config is also in ``tests/vars-example.yaml``. You should run it
(``pav run vars-example``) and look at the created run script to see how all the variables were
handled.

**NOTES**:

- **ALL** Pavilion variables are limited to the above formats, regardless of where they come from.
- While our example shows indexing the second list item, it's generally unsafe to do so!
  You don't know if there even is a second item. There are plenty of neat ways to deal with all
  items in a list that are safer. We'll cover those below.

Other Variable Sources
~~~~~~~~~~~~~~~~~~~~~~

Pavilion also provides a bunch of variables for you:

'Pavilion' Variables (pav)
^^^^^^^^^^^^^^^^^^^^^^^^^^

'Pavilion' variables are provided by the core of Pavilion itself - it's all stuff that's pretty
system agnostic, like the current user and time.

Use ``pav show pav_vars`` to get a list of them.

'System' Variables (sys)
^^^^^^^^^^^^^^^^^^^^^^^^

'System' variables are variables that provide information that may be system specific in
how you get it. Pavilion provides a few of these by default.

Use ``pav show sys_vars`` to get a list of them.

If the name starts with 'host', they are specific to the head node of the allocation the test is
actually running on. If the name starts with 'sys', they're meant to be a cluster-wide value.
Some of them are deferred, meaning Pavilion won't know the value until it's running on an
allocation.

'Scheduler' Variables (sched)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Scheduler variables are provided by the scheduler plugin. Despite being scheduler specific, they
are *mostly* uniform across scheduler plugins.

Use ``pav show sched`` to see a list of available scheduler plugins, and
``pav show sched --vars <sched_name>`` to see the scheduler variables for a particular
scheduler, with example values.

These have a naming convention too - The 'test\_' prefix denotes that the values are
specific to the allocation the test is actually running on. As such, many of these are
*deferred* as well.

Variable Long Form
^^^^^^^^^^^^^^^^^^

You can access any of the above variables just by their name in a config regardless of where
they come from. But you *can* also specify where the variable came from with the source
prefixes (``sched``, ``pav``, ``sys``, ``var``). This order is important! If the source
isn't specified, later sources in this list will override that value if one is provided.

.. code-block:: yaml

    var-example2:
        variables:
            cookies: "oatmeal"
            user: 'bob'

        run:
            # These two are equivalent (kind-of)
            - echo "I am running on cluster {{sys_name}}"
            - echo "I am running on cluster {{sys.sys_name}}"

            # But these two aren't!
            - echo "{{user}}"       # Will always print 'bob'
            - echo "{{pav.user}}"   # Will print the current user.
            - echo "{{var.user}}"   # Will also always print 'bob'

This allows you to specify the source if needed, but also allows you to override values
of variable provided by sources with lower priority.

Variables Can Contain Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can build up variables from multiple sources. Order doesn't matter, just don't create
any reference loops!

.. code-block:: yaml

    var-example3:
        variables:
            flags: '-a -b -c'
            cmd: './run-this {{flags}} -u {{user}}'

Expressions
~~~~~~~~~~~

Variable references are actually an 'expression block', and contain full mathematical expressions
and some function calls.

 - Basic operations (+, -, /, \*, ^) are supported, as are logic operations (AND, OR, NOT),
   as well as grouping with parenthesis.
 - Multiple variable names may be referenced in each expression block.
 - Types are figured out automatically - If it looks like an int, it becomes an int.
   'True' and 'False' are also read as booleans.

Functions are also available. To get a list of available functions for Pavilion expressions,
run ``pav show functions``. Many of these functions take lists of values. Giving '*' as the
index value for the variable (ie ``myvar.*``) will return a list of values.

**Change your test to look like this:**

.. code-block:: yaml

    basic:

    # ...

    variables:
        people:
            - Robert
            - Suzy
            - Yennifer
        base: 3
        exponent: 7
        constant: 5.3

    run:
        cmds:
            - 'echo "Doing some math: {{ (base ^ exponent) - constant }}"'
            # Giving '*' as the list index on any variable gives the whole list.
            - 'echo "Saying hello to {{len(people.*)}} people."'
            # We insert the user into our test.
            - './hello {{people.0}} {{people.1}} {{people.2}}'

Run the above ``pav run tutorial``, and look at the output of the run script (``pav log run
<test_id>``). You'll see that our math was done, and the 'len' function gave the length of
our people list. While this is a silly, contrived example, it shows the power of the expression
blocks in Pavilion, and we'll be using these expressions more in the advanced result parsing
tutorial (:ref:tutorials.extracting_results)

Writing Generic Tests using Hosts and Modes Files
-------------------------------------------------

When writing a test wrapper script, a common goal is to make it 'system agnostic' - independent
of the configuration of the system its running on. The primary way to do this is to move
any system specific information into variables, and provide the value of those variables through
the host configuration.

Host files, which are placed in the ``<configs>/hosts/`` directory, provide that functionality.
Each host file is like a single test configuration that forms the defaults for all tests run on
that system. Values in the test config will override these defaults (see below for a way around
this).

**Let's create our first host file.**

First you need the name of your host, from Pavilion's perspective. Run ``pav show sys_vars``,
and look at the value of the ``sys_name`` variable. Pavilion strips out any trailing numbers
in the name (multiple frontends on the same cluster are considered the same 'host'). Create
a file based on that name in the ``hosts/`` directory: ``hosts/<sys_name>.yaml``.

Put the following into that file:

.. code-block:: yaml

    # Unlike with test suite configurations, there is no top level test name mapping

    # We're providing some variable values at the host level. These will be
    # available for every test that runs on that host.
    variables:
        people:
            - Robert
            - Suzy
            - Dave
            - Isabella

Then, in your ``tests/tutorial.yaml``, erase the people variable in your variables section.
Now run your test. ``pav run tutorial``

When you look at the output (``pav log run <test_id>``), you'll see that it now prints the
names from our host file instead of the three names that were originally in our test's variables.

BUT WAIT! What about the last name? It's missing. We'll show how to write our tests to
dynamically handle any number of items like this in a bit.

Keeping Host Variables Simple
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To keep this host configurations simple, you should try to design these variables such that their
usable across multiple tests. For instance, you might have a list of filesystems that need to
be tested, or a list of compilers that test software should be built against.

Additionally, you should calculate values wherever possible. For instance, if a problem size
should scale with the number of cores on a machine, try using the ``test_min_cpus`` scheduler
variable rather than relying on host based settings. For example:
``{{ floor(test_min_cpus / 2) }}``.

To keep it even more simple, you should also provide sensible defaults for all of these variables
in the test themselves, that way the host configuration need only set those values that are needed.
To provide defaults in a test, append a '?' to the variable's name - this will tell Pavilion to
only use that value if another value wasn't provided already. You can use this to provide a
sensible default, or leave it empty to denote that a value *MUST* be provided by the host file.

**Edit your test to look like this:**

.. code-block:: yaml

    basic:
        # ...
        variables:
            # ...
            # You can also provide an empty list or no value.
            people?:
                - Default_human

Mode Files
~~~~~~~~~~

Mode files are the opposite of host files - they provide a way to override anything provided by
the host file or test itself. These are usually used to override scheduler parameters in certain
situations. They have the exact same format as host files, But are applied using the
``--mode/-m`` option: ``pav run -m gpu_partition mytests``. You can apply more than one mode
file, if needed.

Examining the Final Test Config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given all these layers and variables, sometimes it's hard to make sense of what the final
test config will look like. To get a view of it, use the ``pav view`` command. It will show you
the final test configuration.

**Try it now**  ``pav view tutorial``

List Expansions, Permutations, Inheritance
------------------------------------------

Pavilion provides several ways to dynamically adapt tests for varying circumstances.

List Expansions
~~~~~~~~~~~~~~~

When we added the host file, we saw that the fourth name wasn't being used in our run command. It
could have been worse! If we had had less names, Pavilion would have thrown an error due to the
missing third value. Let's fix our test to handle any number of people, including zero!

List Expansions allow you to repeat a piece of text for every value in a variable list. It works
even if the value isn't a list (technically, variables are always lists of 1 or more values), and
if that list is empty!

To do so, we use the special list expansion syntax.
**Change your test run commands to look like this:**

.. code-block::

    basic:
        run:
            cmds:
            - 'echo "Doing some math: {{ (base ^ exponent) - constant }}"'
            - 'echo "Saying hello to {{len(people.*)}} people."'

            # Each of the people will be listed, including the trailing space.
            - './hello [~{{people}} ~]'

Run your test, and check the output. It should now be printing all 4 people from your host file.

Note the trailing space after ``{{people}}``. It will be included in each of the repetitions,
providing a defacto separator. If you want an actual separator, you can insert one between the
closing tilde and bracket, like this: ``$PATH:[~{{PATHS}}~:]``, which would produce something like
``$PATH:/path1:/path2``.

Inheritance
~~~~~~~~~~~

Inheritance lets us create a new test based mostly on another test in the same suite. This
allows us to create the foundation for the test, then create variations on how to run that test.
Sometimes a very different system type will require changes to a test beyond what we can handle
with just a host file, for instance.

To inherit from a test, just use the ``inherits_from`` key in your test.

**Let's try that now. Create new test in your tutorial test suite:**

.. code-block:: yaml

    basic:
        # Leave the basic test alone for now.

    big_numbers:
        inherits_from: basic

        variables:
            # We're going to override these variables in our original test.
            base: 33
            exponent: 40
            constant: 25

            # Lists of values are completely overridden.
            people:
                - Dave

And that's it. The new 'big_numbers' test will use everything set under 'basic', but override
all those variables we set. You can override anything from the base test config, from test commands
to scheduler parameters.

Now that we have two tests in the suite, running ``pav run tutorial`` will run both of them. To
run just one or the other, give the full test name such as ``pav run tutorial.big_numbers``.

More Inheritance
^^^^^^^^^^^^^^^^

It's often useful to include a test that acts as the base for all other tests in the suite, but
is never meant to be run itself. You can make a test **hidden** by prepending an underscore to
its name, such as ``_base``. You can still inherit from such tests, but when you run the whole
test suite hidden tests aren't run.

You can also inherit in a chain. 'testc' can inherit from 'testb' which inherits from 'testa'.

Permutations
~~~~~~~~~~~~

Permutations are kind of like list expansions, except they make an entire new test for every
value permuted over! To use this, set the ``permute_on`` option to any (non-deferred) variable -
One test will be created for each value of that variable, and in that test the variable will only
contain that single value.

**Let's try that now. Add a new inherited, permuting test to your config:**

.. code-block:: yaml

    permuted_example:
        # We'll create a test for every person in the people list.
        permute_on: people

        # The tests will be just like the basic test, except the people
        # 'people' variable will have a single value in each (for each different person in
        # the people list).
        inherits_from: basic

That was easy - let's run it.  ``pav run --status tutorial.permuted_example``
I added a '--status' to give us an immediate status print out. How did we live without that?

A few things to note:

- There's one test for each of the 'people'!
- The person is included in the test name. Nice.

Multiple Variables
^^^^^^^^^^^^^^^^^^

You can actually provide a list of values to ``permute_on``. In that case you'll end up with a
test for every combination of those lists. So if you specified two lists with three values each
(``['a', 'b', 'c'] and ['1', '2', '3']``) you'd end up with nine tests: ``'a1', 'a2', 'a3', 'b1',
...``  This is actually true of list expansions too, just less useful there.

Complex Variable Permutations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also permute (and list expand) over complex variables too, but how do we choose a
what to call each permutation? By default, Pavilion picks the first key alphabetically. If that's
not what you want, you can specify that name manually"

.. code-block:: yaml

    ex2:
        permute_on: complex_user
        # This will be the last component of the test's name.
        subtitle: "{{complex_user.name}}"

        variables:
            complex_user:
                - name: bob
                  uid: 32
                - name: suzy
                  uid: 37

        run:
            cmds:
                - 'echo "Hi {{compex_user.name}}"

Scheduling
----------

If it weren't for scheduling, there really wouldn't be much of a point to Pavilion. After all,
there are numerous test frameworks that work just fine. Pavilion is all about setting tests
up to run on clusters, and that comes with its own set of problems not handled by most test
harnesses.

So far we've been using the 'raw' scheduler, which simply kicks tests off as on the command line
on the local machine. The basic operation is the same though, so let's start there.

What does Pavilion do to 'kickoff' tests? Pretty much the same thing, regardless of scheduler.

    1. Ask the scheduler about its nodes.
    2. Filter the nodes by the 'schedule' parameters to figure out what nodes to run on.
    3. Give the test the scheduler variables.
    4. Create a 'job' for the test run.
    5. Write a 'kickoff' script for the test run.
    6. Call the command to 'schedule' the kickoff script.
    7. The kickoff script then runs pavilion again to run the given test_run on the machine.

Basic schedulers like 'raw' skip steps 1 and 2, which if done, enables a bunch of neat features
we'll talk about later.

** Do this **
Look at the contents of your last run test ``pav ls <test_id>``. You'll see a 'job' directory. We
can look at the contents of that with ``pav ls <test_id> job``. It contains the kickoff script,
kickoff log, and a directory of symlinks back to the job's tests (a job can have more than one
test).

Cat the kickoff script: ``pav cat <test_id> job/kickoff``. In the case of the raw scheduler, the
kickoff script only needs to set up the environment for Pavilion and then use the top secret
``_run`` command to start test_run number 16. If the job has more than one test to run, it will
simply kick each of them off in turn. All output from this script is sent to the kickoff log,
which is a good place to look (with ``pav log kickoff <test_id>``) when something goes wrong with
scheduling.

Running a Test Under A Cluster Scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**NOTE**: This section requires a cluster using the Slurm scheduler.

We're now going to run our test under Slurm. Not a whole lot needs to change.

    1. We need to set the scheduler to 'slurm'.
    2. We need to set scheduler parameters to appropriate values.
    3. We need to run the test on all the nodes in the allocation.

Most of steps 1 and 2 can be done in host or mode files. Tests that need the raw
scheduler can set that in the test itself as an exception to the rule. Parameters that
you always use when testing a host, such as the QOS, partition, account, etc should
be set in the host file. Slurm parameters that you occasionally use can be set up in
their own mode files.

For instance, when regression testing machines we use a special 'maintenance' reservation. So
we've but that (and the additional related parameters) in a 'maint' mode file that we use in
those circumstances.

**Do this**

In your host file for this machine, set the ``scheduler`` option to 'slurm', and
set additional slurm parameters as needed for your machine. See ``pav show sched --config`` for
a listing of all options that go in the ``schedule`` section and their documentation.

You should end up with a host file that includes something like this:

.. code-block:: yaml

    scheduler: slurm
    schedule:
        # These will depend on your system. You shouldn't rely on your account
        # defaults - Pavilion will choose its own defaults that might not match yours.
        qos: standard
        partition: standard
        account: myteam

Pavilion will use these parameters to query Slurm about the systems, and filter out any nodes
that don't match. This gives Pavilion an explicit list of nodes that can be allocated, which lets
us use keywords like 'all' or percentages when asking for nodes.

**Also do this**

In your test, add a scheduler as well and tell the test how man nodes to request. We're assuming
you're already the expert on what constitutes a reasonable request.

We also need to run our test under the task scheduling command - typically 'srun'. Pavilion does
most of the work of determining what that command should look like, and puts that in the
``test_cmd`` scheduler variable. You can safely use this with any scheduler - for 'raw' it's blank,
and the Slurm scheduler config has options to use 'mpirun' instead.

.. code-block:: yaml

    basic:
        # ...

        # We need to override the scheduler set in the host file for most of these.
        scheduler: raw

    slurmy:
        inherits_from: basic

        run:
            cmds:
                # We're going to overwrite the whole command list, and just do the hello command.
                # {{test cmd}} will get replaced with an 'srun' invocation
                - '{{test_cmd}} ./hello {{people}}'

        # We need to override the 'raw' setting from basic, which we inherited from. Usually
        # it's not this convoluted.
        scheduler: slurm
        schedule:
            # You can give an absolute number, the keyword 'all' (all UP nodes), or a percentage
            # (the percentage of UP nodes)
            nodes: 2

Now let's try running it: ``pav run tutorial.slurmy``. You can keep an eye on the test's status
with ``pav status`` as normal, it will track the job in the slurm queue, and tell you when it
has started running. Depending on your cluster, it may take a bit of time for slurm to actually
decide to run your test.

You can look at the output as we have before, but you should also take a look at the kickoff
script for the test (``pav cat <test_id> job/kickoff``). You'll quickly notice that it's very
similar to the 'raw' kickoff script before, except with a full complement of 'sbatch' headers.

Cancelling Tests
^^^^^^^^^^^^^^^^

The ``pav cancel`` command can be used to cancel specific tests, or the entire test 'series' that
you started with an invocation ``pav run``. When cancelled by Pavilion, the tests will be marked
as complete, their run will be stopped under the scheduler, and if all tests in a job are
cancelled, the slurm job will be cancelled as well. See ``pav cancel --help`` for more.

Debugging Slurm Runs
^^^^^^^^^^^^^^^^^^^^

Your test may fail to run, most likely do to issues with the slurm parameters. Let's talk about
how to debug such issues.

The first step is to take a look at the kickoff log: ``pav log kickoff <test_id>``.
This will give you the output of slurm when sbatch was run on the script.

The most common problem is bad qos, partition, or account settings. Here you'll have to rely on
your own knowledge of the system to find the right combination - Slurm is unfortunately obtuse
about which combinations actually work together. I typically try to launch a job manually until I
find a reasonable combination, and then translate that into the Pavilion configs.

It's also possible that your local cluster users slurm node states that Pavilion doesn't
recognize. Pavilion keeps three lists of state names for Slurm: 'avail_states', 'up_states', and
'reserved_states'. You can redefine these lists as needed under 'schedule.slurm.up_states', etc.

An occasional problem is with node selection with 'features'. Pavilion does not, by default, filter
nodes according to node 'features', but often nodes with different features can't be allocated
together or without specifically requesting the given features. Pavilion provides mechanisms to
do this under Slurm - see the slurm specific 'features' options via ``pav show sched --config``.


More Scheduler Features
~~~~~~~~~~~~~~~~~~~~~~~

Pavilion's scheduler plugins provide quite a few more features than we need to get in here, such
as allocation sharing (on by default), random node selection, testing across consistent system
'chunks', etc. For more information on all of these see the scheduling documentation
(:ref:`tests.scheduling`).

Tutorial Final Test
-------------------

Let's finish off this tutorial by writing a wrapper for a real (albeit lightweight) test:
Supermagic.

The skeleton of a supermagic test config is already in your ``tutorials/tests`` directory, it will
be up to us to finish it.

Let's configure this test not only to build and run, but to check a few filesystems while we're
at it.

Building
~~~~~~~~

Pavilion will automatically extract the zip file listed, and the build root will be the root
directory of that archive.

To build supermagic we will most likely need to load a compiler and mpi, and set CC to the
appropriate mpi compiler wrapper for your system.

Remember: ``pav log build <test_id>`` is your friend here.

Variables
~~~~~~~~~

You should set a 'test_filesystems' variable with paths to a few filesystems you can write to,
including your home directory. To make keep the test runnable by more than just you, make sure to
use {{user}} instead of your user name in paths.

Running
~~~~~~~

We also need to add a 'run' section and commands to our test. Once built, we can run supermagic
with a ``{{test_cmds}} ./super_magic`` command. You will probably also need to load the
same compiler/mpi combo from the build section.

To perform the write test, use the ``-w <path>`` option. You can use *list expansions* or
*permutations* to either provide this argument multiple times or test each path independently.

Result Parsing
~~~~~~~~~~~~~~

There isn't much to parse out of the results of super magic, so let's just rely on it's return
code to determine whether the test passed or failed. As long as your supermagic call is
the last line in your 'run.cmds' section, you should be fine.

Go here (:ref:`tutorials.extracting_results`) for an in-depth tutorial on parsing results.

Conclusion
~~~~~~~~~~

Through this tutorial we learned about making tests generic and a lot of the ways Pavilion
provides to make that easy to do. But that's not all! Check out the full Pavilion documentation
for even more useful options, see the rest of the Pavilion documentation.:

- Skip Conditions (:ref:`tests.skip_conditions`)
- Build Specificity (:ref:`tests.build`)
- File Creation (:ref:`tests.run.create_files`)
- Inherited command extending (:ref:`tests.run.extending_commands`)