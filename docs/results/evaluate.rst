
.. _results.evaluate:

Result Evaluations
==================

This covers the workings of the 'result_evaluate' system in depth.

.. contents::

Type Conversion
---------------

Variable values are automatically treated as the type they most resemble. This
conversion is applied both to constants and the contents of variables.

- 3.59 -> float
- 3 -> int
- True -> boolean 'True'
- "hello" -> string
- hello -> variable

Complex Variable References
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The result JSON isn't necessarily a flat dictionary. It may contain lists,
other dictionaries, lists of dicts containing lists, and so on.  To get to
deeper keys, you simply provide each step in the path in a dot-seperated name.

For example, given a result structure that looks like:

.. code-block:: json

    {
        "name": "example_results",
        "table": {
            "node1": {"speed": 30.0, "items": 5},
            "node2": {"speed": 50.0, "items": 4},
            "node3": {"speed": 70.0, "items": 3}
        },
        "sched":{
            "test_nodes": 3,
            "test_node_list": ["node1", "node2", "node3"],
        }
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
            message: "Hiya"

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
            # This will become: 'len("Hiya")'
            # Which will evaluate to ``4``.
            # WITHOUT QUOTES - it would be 'len(Hiya)', and the evaluation
            # step would try to look up 'Hiya' as a variable.

            # You can actually include more complex expressions in both
            # the string expression and the evaluation, but this should be
            # avoided
            complicated: '(num * {{ base^10 }})/100'
            # The value string resolves to: '(num * 1024)/100'
            # Which evaluates to: ``(50 * 1024)/100`` -> ``512.0``

