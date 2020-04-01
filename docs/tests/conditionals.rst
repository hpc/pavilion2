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
specify when a test should be skipped. As the name suggests, a test
will be skipped if anything matching the ``not_if`` conditional
is found.

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
with the key 'sys_os' and the value of 'windows'. Pavilion will resolve
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
for ``not_if``, it only takes 1 match to skip the test. In this case
if the user is either 'calvin' or 'nick', or it's the weekend, or the
operating system is 'linux' the test will be skip..

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
Below contains useful bits of information that can help users customize
their conditional statements.

Deferred Variables
^^^^^^^^^^^^^^^^^^
Deferred Variables in Pavilion are variables the cannot be resolved until
the test is on an allocation. This could be anything from the host
architecture to the number of nodes allocated. Conditional statements can
handle the use of deferred variables. It works by checking if a variable is
deferred and assumes the test is okay to run. This results in test being
progressing until the deferred variable is finalized. It will then check
once more and skip or run accordingly.

Regex
^^^^^

All conditional statement directives have dictionaries that follow them. The
values following the keys in the dictionaries are all interpreted as regex
patterns. Let's look at the following example.

.. code:: yaml
    basic_regex_test:
        only_if:
            user: ['^[a-z]+$']
        run:
            cmds:
                ...

In this example the value following the key 'calvin' is a regex pattern
matching a lowercase string containing 1 or more letters a through z.
Obviously in this case any user with capital letters, numbers, or special
characters would not be able to run the test. This is a very powerful features
as rather than listing every single user who should run a test, if you match them
all under a single regex pattern you can greatly simplify your test config.

Just because you can use advanced regex patterns doesnt mean you have to. Let's
see how pavilion handles the following example.

.. code:: yaml
    basic_regex_test:
        only_if:
            user: ['calvin']
        run:
            cmds:
                ...

The pattern 'calvin' is valid regex but can match to multiple values such as
 'calvin' or 'calvinsmith'. Pavilion handles this by taking every value and
making it an explicit regex pattern by adding the regex directives `^` and `$`.
Now `calvin` is interpreted as '^calvin$` and the only_if condition will run
as desired.

Keep in mind by introducing regex users can make mistakes that cause
tests to skip or run when shouldn't. Make sure you have a good handle on regex
before using advanced patterns in your test config. 