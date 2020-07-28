.. _tests.skip_conditions:

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
        # This basic test has two keys to resolve under only_if.
        # Both 'user' and 'weekday' need to match in order to run the test.
        only_if:
            # This test will run if the user is calvin
            "{{user}}": ['calvin']
            # This test also needs the weekday to be MWF to run.
            "{{weekday}}": ['Monday', 'Wednesday', 'Friday']
        run:
            cmds:
                ...

Deferred Variables
^^^^^^^^^^^^^^^^^^

Deferred variables are allowed in the only_if and not_if sections. Such
conditions won't be evaluated until after the test is granted an
allocation, so a test may only be ``SKIPPED`` right before it starts to
run on an allocation. For additional information see
:ref:`tests.variables.deferred`.


not_if
~~~~~~

``Not_if`` differs from ``only_if`` by checking if one conditional
match can be found. If a match is found the test is assigned
the status of ``SKIPPED``:

.. code:: yaml

    basic_test:
        # This basic test resolves two keys under not_if.
        not_if:
            # This test will be skipped if 'sys_os' is windows.
            "{{sys_os}}": ['windows']
            # This test will be skipped if 'user' is calvin or nick.
            "{{user}}": ['calvin', 'nick']
        run:
            cmds:
                ...

Variables
~~~~~~~~~

The keys in the only_if and not_if sections can contain Pavilion
variable references (unlike keys in the rest of Pavilion test
configs). You can even have keys that reference multiple
variables and static characters such as: "Lunix-{{sys_os}} {{user}}".
More on :ref:`tests.variables`.

Regex in Conditional Skips
~~~~~~~~~~~~~~~~~~~~~~~~~~

Values given in conditional skip sections are interpreted as a regex
patterns. The regex value must FULLY match the key associated with it:

.. code:: yaml

    basic_regex_test:
        # In this example we see keys accepting regex patterns.
        only_if:
            # This test will run if the user is a lowercase [a-z] word.
            "{{user}}": ['^[a-z]+$']
            # This test will only run if the 'sys_os' is linux.
            # Pavilion keys must be fully matched by the regex.
            "{{sys_os}}": ['linux']
        run:
            cmds:
                ...