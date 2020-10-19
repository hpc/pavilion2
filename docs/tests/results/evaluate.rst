.. _tests.results.evaluate:

.. contents::

Result Evaluations
==================

In addition to the points made in :ref:`tests.results.basics.evaluations`,
there are a few other notable features and constraints with result
evaluations.

Type Conversion
---------------

Variable values are automatically treated as the type they most resemble. This
conversion is applied both to constants and the contents of variables.

- 3.59 -> float
- 3 -> int
- True -> boolean 'True'
- "hello" -> string
- hello -> variable
- You can refer to deeply nested values using dot notation:

Complex Variable References
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The result JSON isn't necessarily a flat dictionary. It may contain lists,
other dictionaries, lists of dicts containing lists, and so on.  To get to
deeper keys, you simply provide each step in the path in a dot-seperated name.

For example, given a result structure that looks like:

.. code-block:: json

    {
        "name": "example_results",
        "table":
            "node1": {"speed": 30.0, "items": 5},
            "node2": {"speed": 50.0, "items": 4},
            "node3": {"speed": 70.0, "items": 3}
        "sched": {
            "test_nodes": 3,
            "test_node_list": ["node1", "node2", "node3"],
    }

- "table.node1.speed" - Would refer to the 'speed' key of the 'node1' dict which
  is itself a key in the 'table' dict. (It has value ``30.0``).
- "sched.test_node_list.1" - Would refer to the second item in the node list.
  ('node2' in this case)

Pulling Lists of Values
^^^^^^^^^^^^^^^^^^^^^^^

You can also use a single '*' in a variable name to return a list of every
matching value.

- "table.*.speed" -> [30.0, 50.0, 70.0]
- "test_node_list.*" -> ["node1", "node2", "node3"]

  - Which is the same as "test_node_list" by itself, actually.

To get the keys of a dictionary, use the ``keys`` function. The keys are
guaranteed to be in the same order as the values produced when using a '*'.

A Complex Example
^^^^^^^^^^^^^^^^^

Given a test that produces values per node and gathers them using the result
parser :ref:`tests.results.per_file` feature, you may want to use all of
those values to calculate an average or outliers.

.. code-block:: yaml

    multi_val:
        slurm:
            num_nodes: all

        run:
            # Get the root filesystem usage per node.
            cmds: '{{test_cmd}} -o "%N.out" df /'

        result_parse:
            regex:
                used:
                    regex: '^rootfs\s+\d+\s+(\d+)'
                    files: '*.out'
                    per_file: 'name'

1. This will give us a ``<node_name>.out`` file for each node with the command
   output.
2. The result parser will parse out the 3rd column from the 'rootfs' line from
   each of these files.
3. The 'per_file' option of 'name' will store these results in the 'n'
   dictionary by the root filename.

The results will look like:

.. code-block:: json

    {
        "name": "examples.multi_val",
        "n": {
            "node01": {"used": "709248"},
            "node03": {"used": "802218"},
            "node04": {"used": "699320"},
            "node05": {"used": "2030531"},
        },
        "etc": "...",
    }

We could then add the following to our test config to perform calculations
on these values.

.. code-block:: yaml

    multi_val:
        # ...

    result_evaluate:
        mean_used: 'avg(n.*.used)'
        outlier_data: 'outliers(n.*.used, keys(n), 1.5)'
        outliers: 'keys(outlier_data)'

Would give us results like:

.. code-block:: json

    {
        "name": "examples.multi_val",
        "n": {
            "node01": {"used": "709248"},
            "node03": {"used": "802218"},
            "node04": {"used": "699320"},
            "node05": {"used": "2030531"},
        },
        "mean_used": 1060329.25,
        "outlier_data": {"node05": 1.7276},
        "outliers": {"node05"},
    }

String Expressions in Result Evaluations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pavilion variables and string expressions ('{{ stuff }}') can be used,
carefully, in result evaluations. Keep in mind that they are evaluated as a
separate step (using pavilion variables), and will become the string that is
later evaluated in result evaluations.

.. code-block:: yaml

    expr_eval:

        variables:
            num_var: 'num'
            num: 8
            base: 2
            message: "hello world"

        result_evaluate:
            # Set the result 'num' key to 52
            num: '50'

            half_num: '{{num_var}}/2'
            # After strings are resolved, this will become:
            # 'num/2'
            # This will then be evaluated, and the 'num' result value will be
            # used (50).
            # The result 'half_num' key will thus be 25. (ie: ``50/2`` )

            # If we want to include a Pavilion variable as a string, it must
            # be put in quotes.
            msg_len: 'len("{{message}}")'
            # This will become: 'len("hello world")'
            # Which will evaluate to ``11``.

            # You can actually include more complex expressions in both
            # the string expression and the evaluation, but this should be
            # avoided
            complicated: '(num * {{ base^10 }})/100'
            # The value string resolves to: '(num * 1024)/100'
            # Which evaluates to: ``(50 * 1024)/100`` -> ``512.0``

