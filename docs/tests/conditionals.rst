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
architecture, say ``aarm64``, they can simply add
``only_if: {sys_arch: 'aarm64'}``. The test will then only run when that
condition is met.


only_if
~~~~~~~

The ``only_if`` section of the pavilion test config allow users to
specify a series of conditions. As the name would suggest, the test
will run if and only if ALL conditions are met. A test that fails
to meet these conditions will still be created but wil not be run
or built, it will be assigned the status of ``SKIPPED``.

The ``only_if`` directive is followed by a
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

    In this example the dictionary following 'only_if' has a key 'user'
    and the value of 'calvin'. Pavilion will resolve the key and
    check who the actual user is. Pavilion will then compare the resolved
    key with the value and if 'user == calvin' then the test will run
    as 'calvin == calvin'.

Conditional statements can also parse dictionaries with multiple keys
and values, let's look at a more complicated test.

.. code:: yaml

    advanced_test:
        only_if:
            user: ['calvin', 'paul']
            weekday: ['Monday', 'Wednesday', 'Friday']
        run:
            cmds:
                ...

    In this example we have two keys that need to be resolved, user and
    weekday. As with the simpler example above, each key is
    resolved and checked with the values supplied to it. An important
    thing to remember is 'only_if' needs to have a match on ALL keys.
    If the user is paul but it's Tuesday,the test will not run.

not_if
~~~~~~

The ``not_if`` section of the pavilion test config behaves exactly
like the ``only_if`` section except for one main difference. The
test will be assigned the status of ``SKIPPED`` if at least one
conditional match is found. Let's take a look at an example:

.. code:: yaml

    basic_test:
        not_if:
            sys_os: ['windows']
        run:
            cmds:
                ...

    In this example the 'not_if' directive is followed by a dictionary
    with the key 'sys_os' and the value of 'windows'. Pavilion will resolve
    the key and check what the operating system on the machine is. If
    sys_os resolves to 'windows' then the 'not_if' conditions has a match
    and the test will be skipped.

Conditional statements can also parse dictionaries with multiple keys
and values, let's look at a more complicated test.

.. code:: yaml

    advanced_test:
        not_if:
            user: ['calvin', 'nick']
            sys_os: ['linux']
        run:
           cmds:
               ...

    In this example Pavilion will need to resolve two keys, user,
    sys_os. When the keys are resolved they will be compared
    to the dictionary values supplied to them. It is important to note
    for 'not_if', it only takes 1 match to skip the test. In this case
    if the user is either 'calvin' or 'nick', or the operating system
    is 'linux', the test will be skip.

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

Deferred Variables in Pavilion are variables that cannot be resolved
until after an allocation, for example host_arch and number of nodes.
Conditionals handle this by evaluating the test twice, on the second
attempt all deferred variables will have been resolved. The test will
then be properly assigned to ``SKIPPED`` if needed.

Mixed Use
^^^^^^^^^
The ``not_if`` and ``only_if`` directives can be used in conjunction with
one another. The easiest way to see this is by example:

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

Regex
^^^^^

All conditional statement directives have dictionaries that follow them. The
values following the keys in the dictionaries are all interpreted as regex
patterns. Let's look at the following example:

.. code:: yaml

    basic_regex_test:
        only_if:
            user: ['^[a-z]+$']
        run:
            cmds:
                ...

    In this example the value following the key 'user' is a regex pattern
    matching a lowercase string containing 1 or more letters a through z.
    Regex can simplify your test config if you have multiple values to add
    that can be encompassed in a single regex pattern.

Just because you can use advanced regex patterns doesnt mean you have to. Let's
see how pavilion handles the following example:

.. code:: yaml

    basic_regex_test:
        only_if:
            user: ['calvin']
        run:
            cmds:
                ...

    The pattern 'calvin' is valid regex but can match to multiple values such
    as 'calvin' or 'calvinsmith'. Pavilion handles this by taking every value and
    making it an explicit regex pattern by adding the regex directives `^` and `$`
    denoting the start and end of the string. Now 'calvin' is interpreted
    as '^calvin$' and the only_if condition will run as desired.
