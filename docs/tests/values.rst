.. _tests.values.config_values:

Config Values
=============

All of the values in a Pavilion configuration are parsed and resolved. They
can contain *expressions* and *iterations*, which let Pavilion dynamically
alter the each test configuration.

.. contents::

.. _tests.values.expressions:

Environment Variables
---------------------

Environment variables can be used in Pavilion configs **only** in certain
areas that will be written to a run or build script. This is limited to
the 'cmds' and 'env' values under either 'run' or 'build'.

Anywhere else, you must use Pavilion variables. If there's an environment
variable you need, consider capturing it using a
:ref:`system variable plugin <plugins.sys_vars>`.

Expressions
-----------

Expressions are contained within double curly braces. They can contain
:ref:`variable references <tests.variables>`, function calls, and math
operations.  **Expressions often behave similarly to Python3, but they are
not Python3 code.**


.. code-block:: yaml

    expr_test:
        variables:
            # Note that this is a string. Math operations will convert it
            # to a number automatically.
            min_threads: "5"

        run:
            env:
                # Whitespace within expression blocks is ignored.
                # Expression blocks always result in a string value.
                OMP_NUM_THREADS: '{{ min( [min_threads, sched.min_ppu] ) }}'
            cmds:
                # In the simple case, expressions are often just a variable
                # reference.
                - "{{sched.test_cmds}} ./my_cmd"

Types of Expressions
^^^^^^^^^^^^^^^^^^^^

This documentation covers expressions within the context of Pavilion value
strings. They may also be used, with the exact same syntax (but using result
keys as variables), in the 'result_evaluate' section. See
:ref:`results.evaluate`.

Supported Math
^^^^^^^^^^^^^^

Pavilion expressions support most common math operations, and they behave
identically to Python3 (with one noted exception). This includes:

- Addition, subtractions, multiplication and division. ``a + b - c * d / e``.
- Floor division ``//`` and modulus ``%`` operations. ``4.0 // 3``
- Power operations, though Pavilion uses ``^`` to denote these. ``a ^ 3``
- Logical operations ``a and b or not False``.
- Parenthetical expressions ``a * (b + 1)``

List Operations
```````````````

When using math operations with list values, the operation is applied
recursively to each element. Operations between two lists require that the
lists be equal length, and apply the operation between each corresponding pair
of items.

.. code-block::

    list_expr_test:
        variables:
            nums: [1, 2, 3, 4]
            mult: [4, 4, 2, 1.5]

            # This would add 3 to each value in the num list, then take average.
            # The result would thus be (4 + 5 + 6 + 7)/4 == 5.5
            avg_adj_nums: '{{avg(nums + 3)}}'

            # This would produce (1*4 + 2*4 + 3*2 + 4*1.5)/4 == 6.0
            mult_avg: '{{avg(nums*mult)}}'


Types and End Results
^^^^^^^^^^^^^^^^^^^^^

Math operations handle ints, floats, and booleans (``True`` and ``False``).
Variable values are always strings, but are auto-converted as if they were
literal ints, floats or booleans when used in math or logic operations.

Strings, lists (of these types) and dictionaries/mappings are allowed as well.
While they can't be used in math operations, they are often useful in as
function arguments.

The final result of an expression cannot be a list or dict - this will result
in an error.

Result Formatting
`````````````````

Expressions can be formatted using printf-like format codes. These are put at
the end of the expression after a colon:

.. code-block:: yaml

    format_test:
        variables:
            # The chunk size will be the square root of sys_nodes, to three
            # decimal places.
            chunk_size: "{{ sched.sys_nodes^(0.5) :0.3f}}"
            # The id will be the current time zero-padded to 10 digits.
            id: "{{pav.timestamp:010d}}"

Formatting behaves exactly like `Python format specs`_, because that's exactly
what they are.

.. _Python format specs: https://docs.python.org/3.4/library/string.html#formatspec

.. _tests.values.functions:

Functions
^^^^^^^^^

Functions can be used within expressions as well.

- Functions are all :ref:`plugins.expression_functions`.
- Available functions can be listed with ``pav show functions``.
- Functions auto-convert argument types as appropriate.

.. _tests.values.iterations:


Iterations
----------

Iterations give you the ability to insert that string once for every
value of a contained variable. They're bracketed by ``[~`` and ``~]``.

.. code-block:: yaml

    substr_test:
        variables:
          dirs: ['/usr', '/root', '/opt']

        run:
          cmds: 'ls [~{{dirs}}/ ~]'

This would result in a command of ``ls /usr/ /root/ /opt/``. Note that
the trailing ``/`` and space are repeated as well.

.. code-block:: yaml

    super_magic_fs:
        variables:
          projects: [origami, fusion]

        run:
          cmds: 'srun ./super_magic [~-w /opt/proj/{{projects}} ~] -a'

This would get us a command of:
``srun ./super_magic -w /opt/proj/origami -w /opt/proj/fusion  -a``

Iteration Separators
^^^^^^^^^^^^^^^^^^^^

In the above examples, the trailing space from the iteration resulted in
an extra space at the end. That's fine in most circumstances, but what
if we need to separate the strings with something that can't be repeated
at the end?

To do that, simply insert your separator between the tilde ``~`` and
closing square bracket ``]``. The separator can be of any length, and any
closing square brackets need to be escaped (``\]``).

.. code-block:: yaml

    substr_test2:
        variables:
          groups: [testers, supertesters]

        run:
          cmds: 'grep --quiet "[~{{groups}}~|]" /etc/group'

The command would be: ``grep --quiet "testers|supertesters" /etc/group``

Multiple Variables
^^^^^^^^^^^^^^^^^^

Iterations can contain multiple variables, in which case the iteration will
be repeated for every combination of the variable values.

.. code-block:: yaml

    super_magic_fs:
        variables:
          projects: [origami, fusion]
          test_users: [bob, jane]

        run:
          cmds: 'srun ./super_magic [~-w {{projects}}/{{test_users}} ~]'

This would result in the command:

.. code-block:: none

    srun ./super_magic -w origami/bob -w fusion/bob -w origami/jane -w fusion/jane

Direct Variable Access
^^^^^^^^^^^^^^^^^^^^^^

In all the iterations we've used so far, the variables were in the form:
``'var.projects'`` or just ``'projects'``. If we want to access a specific
value from a multi-valued variable, we can still do that. You can't, however,
access a specific value from a variable that is being iterated over.

..code-block

    super_magic_fs:
        variables:
          projects: [origami, fusion]
          test_users: [bob, jane]

        cmds:
            # This is ok
            - 'srun ./super_magic [~-w {{projects}}/{{test_users.0}} ~]'
            # srun ./super_magic -w origami/bob -w fusion/bob

            # This is NOT ok, and will cause an error.
            - 'echo "[~{{test_users}} {{test_users.1}} ~]"
