
.. _tests.results:

Test Results
============

Every successful test run generates a set of results in JSON. These are
saved with the test, but are also logged to a central ``results.log``
file that is formatted in a Splunk compatible manner.

These results contain several useful values, but that's just the
beginning. `Result Parsers <#using-result-parsers>`__ are little parsing
scripts that can be configured to parse data from your test's output files.
They're designed to be simple enough to pull out small bits of data, but
can be combined to extract a complex set of results from each test run.
Each result parser is also a `plugin <../plugins/result_parsers.html>`__,
so you can easily add custom parsers for tests with particularly complex
results.

.. toctree::
    :maxdepth: 2
    :caption: Result Parsers

    results/cmd.rst
    results/regex.rst
    results/const.rst
    results/table.rst

Similarly, result analyzers are mathematical expressions that can operate on
the other result values themselves. These can also include arbitrary
:ref:`tests.values.functions` defined via :ref:`plugins.expression_functions`.


Basic Result Keys
-----------------

These keys are present in the results for every test, whether the test
passed or failed.

-  **name** - The name of the test.
-  **id** - The test's run id.
-  **created** - When the test run was created.
-  **started** - When the test run actually started running in a
   scheduled allocation.
-  **finished** - When the test run finished.
-  **duration** - How long the test ran. Examples: ``0:01:04.304421`` or
   ``2 days, 10:05:12.833312``
-  **result** - The PASS/FAIL result of the test.
-  **return_value** - The return value of the run.sh script.

All time fields are in ISO8601 format.

result
~~~~~~

The 'result' key denotes the final test result, and will always be
either '**PASS**' or '**FAIL**'.

By default a test passes if it's run script returns a zero result, which
generally means the last command in the test's ``run.cmds`` list also
returned zero.

This is defined by a default result evaluation of `return_value == 0` for
the 'result' key. The test_run then translates that into to '**PASS**' or
'**FAIL**' keywords.

Result Parsers
--------------

The ``results`` section of each test config lets us configure additional
result parsers that can pull data out of test output files. By default
each parser reads from the run log, which contains the stdout and stderr
from the run script and your test.

.. code:: yaml

    mytest:
      scheduler: raw
      run:
        cmds:
          - ping -c 10 google.com

      results:
        # The results section is comprised of configs for result parsers,
        # identified by name. In this case, we'll use the 'regex' parser.
        regex:
          # Each result parser can have multiple configs.
          - {
            # The value matched will be stored in this key
            key: loss
            # This tells the regex parser what regular expression to use.
            # Single quotes are recommended, as they are literal in yaml.
            regex: '\d+% packet loss'
          }
          - {
            # We're storing this value in the result key. If it's found
            # (and has a value of 'True', then the test will 'PASS'.
            key: result
            regex: '10 received'
            # The action denotes how to handle the parser's data. In this case
            # a successful match will give a 'True' value.
            action: store_true
          }

The results for this test run might look like:

.. code:: json

    {
      "name": "mytest",
      "id": 51,
      "created": "2019-06-18 16:00:35.692878-06:00",
      "started": "2019-06-18 16:00:36.744221-06:00",
      "finished": "2019-06-18 16:01:39.997299-06:00",
      "duration": "0:01:04.304421",
      "result": "PASS",
      "loss": "0% packet loss"
    }

Keys
----

The key attribute is required for every result parser config, as
Pavilion needs to know under what key in the results to store the parsed
result. The default result keys (``id``, ``created``, etc) are not
allowed, with the exception of ``result``.

The ``result`` key
~~~~~~~~~~~~~~~~~~

The result key must always contain either a value of ``PASS`` or
``FAIL``. Setting the ``result`` key allows you to override the default
behavior by setting this value according to the results of any result
parser, but there are a few special behaviors:

-  The result value must be either ``true`` or ``false``.
-  The `action <#actions>`__ must either be **store\_true** or
   **store\_false**. Pavilion overrides the normal **store** default and
   replaces it with **store\_true**.
-  If the ``result`` value is ``true``, ``PASS`` is stored. The result
   is otherwise set to ``FAIL``.

Result Value Types
~~~~~~~~~~~~~~~~~~

Result parsers can return any sort of json compatible value. This can be
a string, number (int or float), boolean, or a complex structure that
includes lists and dictionaries. Pavilion, in handling result values,
groups these into a few internal categories. - **empty** - An empty
result is a json ``null``, or an empty list. Everything else is
**non-empty**. - **match** - A **match** is a **non-empty** result that
is also not json ``false``. - **false** - False is special, in that it
is neither **empty** nor a **match**.

The *actions* and *per\_file* sections below work with these categories
when deciding how to handle result parser values.

Actions
~~~~~~~

We saw in the above example that we can use an *action* to change how
the results are stored. There are several additional *actions* that can
be selected:

-  **store** - (Default) Simply store the result parser's output.
-  **store\_true** - Store ``true`` if the result is a **match**
   (non-empty and not false)
-  **store\_false** - Stores ``true`` if the result is not a **match**.
-  **count** - Count the length of list matches, regardless of contents.
   Non-list matches are 1 if a match, 0 otherwise.

Files
~~~~~

By default, each result parser reads through the test's ``run.log``
file. You can specify a different file, a file glob, or even multiple
file globs to match an assortment of files. The files are parsed in the
order given.

If you need to reference the run log in addition to other files, it is
one directory up from the test's run directory, in ``../run.log``.

This test runs across a bunch of nodes, and produces an output file for
each. The regex parser runs across each of these, and (because it
defaults to returning the first found item only) returns that item or
``null`` for each of the files found. What it does with those values
depends on the **per\_file** attribute for the result parser.

.. code:: yaml

    hugetlb_check:
        scheduler: slurm
        slurm:
          num_nodes: 4

        run:
          cmds:
            # Use the srun --output option to specify that results are
            # to be written to separate files.
            - {{sched.test_cmd}} --output="%N.out" env

        results:
          regex:
            # The matched values will be stored under the 'huge_size' key,
            # but that will vary based on the 'per_file' value.
            key: huge_size
            regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
            # Run the parser against all files that end in .out
            files: '*.out'
            per_file: # We'll demonstrate these settings below

per\_file: Manipulating Multiple File Results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **per\_file** option lets you manipulate how results are stored on a
file-by-file basis. Since the choice here will have a drastic effect on
your results, we'll demonstrate each from the standpoint of the test
config above.

Let's say the test ran on four nodes (node1, node2, node3, and node4),
but only node2 and node3 found a match. The results would be:

- node1 - ``<null>``
- node2 - ``2M``
- node3 - ``4K``
- node4 - ``<null>``

first - Keep the first result (Default)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: first

Only the result from the first file with a **match** is kept. In this
case, the value from node1 would be ignored in favor of that of node2. The
results would contain:

.. code:: json

    {
      "huge_size": "2M"
    }

In the simple case of only specifying one file, the '**first**' result is the
only result. That's why this is the default; the first is all you normally need.

last - Keep the last result
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: last

Just like '**first**', except we work backwards through the files and
get the last match value. In this case, that means ignoring node4's
result (because it is null) and taking node3's:

.. code:: json

    {
      "huge_size": "4K",
    }

all - True if each file returned a True result
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: all

By itself, '**all**' sets the key to True if the result values for all
the files evaluate to True. Setting ``action: store_true`` produces more
predictable results.

+---------------------------+-----------+------------+--------------------+
|                           | value     | t/f value  | action: store_true |
+===========================+===========+============+====================+
| No result                 | ``<null>``| *false*    | *false*            |
+---------------------------+-----------+------------+--------------------+
| Non-empty strings         | ``'2M'``  | *true*     | *true*             |
+---------------------------+-----------+------------+--------------------+
| Empty strings             | ``''``    | *false*    | *true*             |
+---------------------------+-----------+------------+--------------------+
| Non-zero numbers          | ``5``     | *true*     | *true*             |
+---------------------------+-----------+------------+--------------------+
| Zero                      | ``0``     | *false*    | *true*             |
+---------------------------+-----------+------------+--------------------+
| Literal true              | ``true``  | *true*     | *true*             |
+---------------------------+-----------+------------+--------------------+
| Literal false             | ``false`` | *false*    | *false*            |
+---------------------------+-----------+------------+--------------------+

In our example, the result is ``false`` because some of our files had no matches
(a ``<null>`` result).

.. code:: json

    {
      "huge_size": false,
    }

any - True if any file returned a True result
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: any

Like '**all**', but is ``true`` if any of the results evaluates to True. In
the case of our example, since at least one file matched, the key will be
set to 'true'

.. code:: json

    {
      "huge_size": true,
    }

list - Merge the file results into a single list
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: list

For each result from each file, add them into a single list. **empty**
values are not added, but ``false`` is. If the result value is a list
already, then each of the values in the list is added.

.. code:: json

    {
      "huge_size": ["2M", "4K"],
    }

fullname - Stores in a filename based dict.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: fullname

Put the result under the key, but in a dictionary specific to that file. All
the file specific dictionaries are stored under the ``fn`` key by filename.

.. code:: json

    {
      "fn": {
        "node1.out": {"huge_size": null},
        "node2.out": {"huge_size": "2M"},
        "node3.out": {"huge_size": "4K"},
        "node4.out": {"huge_size": null}
      }
    }

-  When using the **fullname** *per\_file* setting, the key cannot be
   ``result``.
-  The rest of the file's path is ignored, so there is potential for
   file name collisions, as the same filename could exist in multiple
   places. Pavilion will report such collisions in the results under the
   ``error`` key.

name - Stores in a filename (without extension) based dict.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: fullname

Just like **fullname**, but instead the file name with the file extension
removed. These are stored under the ``n`` key in the results.

.. code:: json

    {
      "n": {
        "node1": {"huge_size": null},
        "node2": {"huge_size": "2M"},
        "node3": {"huge_size": "4K"},
        "node4": {"huge_size": null}
      }
    }


fullname_list - Stores the name of the files that matched.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: fullname_list

Stores a list of the names of the files that matched. The actual matched values
aren't saved.

.. code:: json

    {
      "huge_size": ["node2.out", "node3.out"],
    }

name_list - Stores the name of the files that matched.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    results:
      regex:
        key: huge_size
        regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
        files: '*.out'
        per_file: name_list

Stores a list of the names of the files that matched, minus extension. The
actual matched values aren't saved.

.. code:: json

    {
      "huge_size": ["node2", "node3"],
    }

Errors
~~~~~~

If an error occurs when parsing results that can be recovered from, a
description of the error is recorded under the ``error`` key. Each of
these is a dictionary with some useful values:

.. code:: yaml

    {
      "errors": [{
        # The error happened under this parser.
        "result_parser": "regex",
        # The file being processed.
        "file": "node3.out",
        # The key being processed
        "key": "hugetlb",
        "msg": "Error reading file 'node3.out': Permission error"
      }]
    }

.. _tests.result.evaluations:

Result Evaluations
------------------

The ``evaluate`` section of the result config is a dictionary of keys and
expressions to evaluate. The result of the expression is stored at the given
key in the result JSON structure. The expressions are evaluated similarly
to the double curly brace expressions that can be used in all Pavilion value
strings, with a few important differences:

- You **don't** put them in double curly braces.
- The value **isn't** converted into a string.

  - Int's stay as ints, etc.
  - Lists and dicts/mappings are allowable results.
- The variables aren't Pavilion variables; they reference other values
  in the result JSON.

.. code-block:: yaml

    basic_evaluation:
        run:
            cmds:
                cat /proc/cpuinfo

        result:
            # Parsers are always run before evaluations, so the keys they set
            # can be used as evaluation variables.
            parsers:
                regex:
                    # Count the number of processors
                    - key: 'cores'
                      action: 'count'
                      regex: '^processor'
                    # Count the number of processors with hyperthreading
                    - key: 'ht_cores'
                      action: 'count'
                      regex: '^flags:.*ht'

            # Analysis values are evaluated in the order given, and can
            # thus refer to each other.
            evaluate:
                # Count only half the hyperthreading cores.
                # Note that the variables are from the results JSON structure.
                physical_cores: 'cores - ht_cores//2'

                # This test is a success if our physical core count is
                # more than 5.
                result: 'physical_cores > 5'

                # All the expression functions are available.
                weird: 'avg([5*random(), 6*random(), 7*random()])

Deeper Result Values and Lists
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The result JSON isn't necessarily a flat dictionary. It may contain lists,
other dictionaries, lists of dicts containing lists, and so on.  To get to
deeper keys, you simply provide each step in the path in a dot-seperated name.

For example, given a result structure that looks like:

.. code-block:: json

    {
        "jobid": "1234",
        "etc...": "...",
        "transfer_times": {
            "10":   {"min": 5.3, "max": 10.4, "avg": "7.0"},
            "100":  {"min": 11.3, "max": 15.4, "avg": "13.1"},
            "1000": {"min": 15.2, "max": 21.3, "avg": "17.5"}
        },
        "n": {
            "node1": {"speed": 47, "procs: 10"},
            "node2": {"speed": 35, "procs: 5"},
            "node3": {"speed": 20, "procs: 10"}
        }
    }

.. code-block:: yaml

    mytest:
        result:
            # Assume we have the result parsers to actually get the above value.
            # A more complete example is below.

            evaluate:
                small_ok: "transfer_times.10.avg < 10"
                large_ok: "transfer_times.1000.avg < 30"

                # You can use the 'keys()' function to grab the keys of
                # of a dictionary.
                nodes: "keys(n)"

                base_speed: "node

Pulling Lists of Values
~~~~~~~~~~~~~~~~~~~~~~~

Lists of values can be dynamically generated by using a '*' in your variable
name, such as ``foo.*.bar``. The name parts up to the star determine where to
find the list/dict of items. The parts after the star denote what element to
pull from each of the values in that list. So ``foo.*.bar``, will return the
'bar' key from each item in the list at 'foo'.

Using the same result JSON as above:

.. code-block:: yaml

    mytest:
        result:
            evaluate:
                # Get a list of every the proc counts from each node.
                procs: "n.*.procs"

                # Get an average of the speeds across all nodes
                avg_speed: "avg(n.*.speeds)"

                # Find outliers that are more 3.0 standard deviations from
                # the mean of the speeds. See the function documentation
                # for more info.
                speed_outliers: "outliers(n.*.speeds, keys(n), 3.0)"

                # Only PASS if there are no outliers.
                result: "len(outliers) == 0"

A Combined Example
------------------

.. code-block:: yaml

    mytest:
        slurm:
            tasks_per_node: 1

        # This will produce a <hostname>.out file for each node containing
        # the contents of that system's /proc/meminfo file.
        cmds: '{{sched.test_cmd}} -o "%N.out" cat /proc/meminfo'

        result:
            parsers:
                regex:
                    # These will look over each of the out files, pull out
                    # the regex value, and store in a per_file dictionary.
                    - key: MemTotal
                      regex: '^MemTotal:\s+(\d+)'
                      files: '*.out'
                      per_file: 'name'
                    - key: MemFree
                      regex: '^MemFree:\s+(\d+)'
                      files: '*.out'
                      per_file: 'name'

        # The two results parsers above will look for the regex in each
        # of the .out files, and store the result by the name of the file
        # (without an extension), which happens to be our node name.
        # This will result in a result JSON structure that looks like.
        # {
        #   'jobid': 4321,
        #   ...
        #
        #   'n': {
        #           'host1': {
        #               'MemTotal': 65559088,
        #               'MemFree': 49359920
        #           },
        #           'host1': {
        #               'MemTotal': 65559088,
        #               'MemFree': 49359920
        #           },
        #           ...

            evaluate:
                avg_free_mem: "avg(n.*.MemFree)"
                free_mem_outliers: "outliers(n.*.MemFree, keys(n), 2.0)"
