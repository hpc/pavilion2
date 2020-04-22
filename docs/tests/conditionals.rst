Skip Conditions
===============

Conditional skip statements allow for tests suites to have tests
that target specific architectures, machines, or Pavilion variables.
By using conditional statements users can have one large test
suite that can run across all systems. If a user has a test
that is specific to a unique architecture, say ``aarm64``,
they can simply add ``only_if: {"{{sys_arch}}": 'aarm64'}``. The
test will only run when that condition is met.


only_if
~~~~~~~

Tests run "only_if" each of the conditions in the "only_if"
config section match. They are otherwise assigned the status
of ``SKIPPED``:

.. code:: yaml

    basic_test:
        only_if:
            "{{user}}": ['calvin']
            "{{weekday}}": ['Monday', 'Wednesday', 'Friday']
        run:
            cmds:
                ...

    In this example the 'only_if' directive has two keys to resolve, 'user'
    and 'weekday'. The test will run if user == calvin AND weekday ==
    Monday, Wednesday, or Friday.

Deferred Variables
^^^^^^^^^^^^^^^^^^

Deferred variables are allowed in the only_if and not_if sections. Such
conditions won't be evaluated until after the test is granted an
allocation, so a test may only be ``SKIPPED`` right before it starts to
run on an allocation. For additional information see
`Deferred Variables <variables.html#deferred-variables>`__.


not_if
~~~~~~

``Not_if`` differs from ``only_if`` by checking if one conditional
match can be found. If a match is found the test is assigned
the status of ``SKIPPED``:

.. code:: yaml

    basic_test:
        not_if:
            "{{sys_os}}": ['windows']
            "{{user}}": ['calvin', 'nick']
        run:
            cmds:
                ...

    In this example the 'not_if` directive has two keys to resolve, 'sys_os'
    and 'user'. Only one match is needed so the test will be
    assigned the status of 'SKIPPED' if the sys_os == 'windows' OR if
    user == 'calvin' OR user == 'nick'.

Variables
~~~~~~~~~

Throughout this documentation variables are synonymous with keys. Keys
being the literal dictionary key supplied after calling ``not_if`` or
``only_if``. It is important to note that the reference of variables
is consistent throughout the yaml test config. Its denoted as "{{var}}"
There are multiple types of
variables supported in Pavilion and for detailed documentation on what
variables to use, and how to create you own variables see
`Variables <variables.html>`__.

Regex in Conditional Skips
~~~~~~~~~~~~~~~~~~~~~~~~~~

Values given in conditional skip sections are interpreted as a regex
patterns. The regex value must FULLY match the key associated with it:

.. code:: yaml

    basic_regex_test:
        only_if:
            "{{user}}": ['^[a-z]+$']
            "{{sys_os}}": ['linux']
        run:
            cmds:
                ...

    In this example the value following the key 'user' is a regex pattern
    matching a lowercase string containing 1 or more letters a through z.
    The 'linux' value is also valid regex, however pavilion resolves this
    regex patter to '^linux$` so that the value must fully match it's given
    key. This means 'linux' will only match to 'linux' and not have partial
    matches to something like; 'rhelinux'
