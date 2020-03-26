Conditional  Statements
=======================

The conditional section of the pavilion config consists of two main
directives, ``only_if`` and ``not_if``. This documentation will cover
how to use them as well as details associated with their use in test
configs.

Why conditional statements? As Pavilion becomes more popularized as an
HPC test harness, the test suites it runs will theoretically grow. It is
unrealistic to manage unique test suites for specific machines. By using
conditional statements users can have one large test suite that can run
across all systems. If a user has a test that is specific to a unique
computer architecture, they can simply add 'only_if arch is unique-arch'.
Conditional Statements can greatly simplify your testing procedure.


only_if
~~~~~~~

The ``only_if`` section of the pavilion test config allow users to
specify a series of conditions. As the name would suggest, the test
will run if and only if ALL conditions are met.

The syntax for writing an ``only_if`` condition is fairly
straightforward. The ``only_if`` directive is followed by a
dictionary that should contain at least one key. The key(s)
should consist of a variable(s) that pavilion can resolve. Below is
a basic example.

.. code:: yaml
    basic_test:
        only_if:
            user: ['calvin']
        run:
            cmds:
                ...

In this example the dictionary following ``only_if`` has a key
``user`` and the value of 'calvin'. Pavilion will resolve the key and
check who the actual user is. Pavilion will then compare the resolved
key with the value and if ``user == calvin`` then the test will run as
``calvin == calvin``.

Conditional statements can also parse dictionaries with multiple keys
and values, let's look at a more complicated test.

.. code:: yaml
    advanced_test:
        only_if:
            user: ['calvin', 'paul']
            sys_os: ['linux']
            weekday: ['Monday', 'Wednesday', 'Friday']
        run:
            cmds:
                ...

In this example we have three keys that need to be resolved: [user,
sys_os, weekday]. As with the simpler example above, each key is
resolved and checked with the values supplied to it. An important
thing to remember is ``only_if`` needs to have a match on ALL keys.
If the user is paul testing on a linux machine, but it's Tuesday,
the test will not run.

not_if
~~~~~~

The ``not_if`` section of the pavilion test config allow users to
specify when a test should be skipped. As name suggests, a test will
be skipped if anything matching the ``not_if`` conditional is found.

The syntax for a ``not_if`` conditional statement is straightforward.
A user will specify the directive ``not_if`` followed by a dictionary
with at least one key in their pavilion test config. The key(s)
should consist of a variable(s) that pavilion can resolve. Below
is a basic example.

.. code:: yaml
    basic_test:
        not_if:
            sys_os: ['windows']
        run:
            cmds:
                ...

In this example the ``not_if`` directive is followed by a dictionary
with the key 'sys_os' and the value of `windows`. Pavilion will resolve
the key and check what the operating system on the machine is. If
sys_os resolves to 'windows' then the ``not_if`` conditions has a match
and the test will be skipped.

Conditional statements can also parse dictionaries with multiple keys
and values, let's look at a more complicated test.

.. code:: yaml
    advanced_test:
        not_if:
            user: ['calvin', 'nick']
            weekday: ['Saturday', 'Sunday']
            sys_os: ['linux']
        run:
           cmds:
               ...

In this example Pavilion will need to resolve three 3 keys, user,
weekday, and sys_os. When the keys are resolved they will be compared
to the dictionary values supplied to them. It is important to note
for ``not_if``, it only takes 1 match to cancel the test. In this case
if the user is either 'calvin' or 'nick', or it's the weekend, or the
operating system is 'linux'.

Mixed Use
~~~~~~~~~

The ``not_if`` and ``only_if`` directives can also be used together
in the same pavilion test config. This allows for far more specific
conditions to run tests. The easiest way to see it is to look at an
example.

.. code:: yaml
    mixed_use_test:
        only_if:
            user: ['francine', 'paul']
            sys_os: ['linux']
        not_if:
            weekday: ['saturday', 'sunday']
            sys_arch: ['aarch64']
        run:
            cmds:
                ...

In this example four keys are resolved. This allows tests to run under
very specific circumstances and is useful is tailoring specific tests
for specific machines.

Variables
~~~~~~~~~

Throughout this documentation variables are synonymous with keys. Keys
being the literal dictionary key supplied after calling ``not_if`` or
``only_if``. There are multiple types of variables supported in Pavilion
and for detailed documentation on what variables to use, and how to create
you own variables see `Variables <variables.html>`__.

Tips & Tricks
~~~~~~~~~~~~~

TODO: regex documentation,
deferred variable example,
