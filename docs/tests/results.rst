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
Each result parser is also a `plugin <../plugins/result_parsers.md>`__,
so you can easily add custom parsers for tests with particularly complex
results.

.. toctree::
    :maxdepth: 2
    :caption: Contents:

    results/cmd.rst
    results/regex.rst
    results/const.rst

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

All time fields are in ISO8601 format.

result
^^^^^^

The 'result' key denotes the final test result, and will always be
either '**PASS**' or '**FAIL**'.

By default a test passes if it's run script returns a zero result, which
generally means the last command in the test's ``run.cmds`` list also
returned zero.

Result Parsers may override this value, but they must be configured to
return a single True or False result. Anything else results in a
**FAIL**.

When using the result key, 'store\_true' and 'store\_false'
`actions <#actions>`__ are the only valid choices. Any other action will
be changed to 'store\_true', and the change will be noted in the result
errors. Similarly,
`per\_file <#per_file-manipulating-multiple-file-results>`__ can only
have a setting that produces a single result ('store\_first' is forced
by default).

Using Result Parsers
--------------------

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
^^^^^^^^^^^^^^^^^^

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
            # This will override the test result
            key: result
            regex: 'HUGETLB_DEFAULT_PAGE_SIZE=.+'
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
but only node2 and node3 found a match. The results would be: - node1 -
``<null>`` - node2 - ``HUGETLB_DEFAULT_PAGE_SIZE=2M`` - node3 -
``HUGETLB_DEFAULT_PAGE_SIZE=4K`` - node4 - ``<null>``

first - Keep the first result (Default)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Only the result from the first file with a **match** is kept. In this
case, the value from node1 would be ignored in favor of that of node2:

.. code:: json

    {
      "hugetlb": "HUGETLB_DEFAULT_PAGE_SIZE=2M",
      "result": "PASS",
      # This would also contain all the default keys, like 'created' and 'id'
      ... 
    }

last - Keep the last result
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Just like '**first**', except we work backwards through the files and
get the last match value. In this case, that means ignoring node4's
result and taking node3's:

.. code:: json

    {
      "hugetlb": "HUGETLB_DEFAULT_PAGE_SIZE=4K",
      "result": "PASS",
      ...
    }

all - True if each file returned a True result
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By itself, '**all**' sets the key to True if the result values for all
the files evaluate to True. This means a result of the number 0 or an
empty string, which may be valid **matches**, will evaluate to
``false``. If you would like matches to evaluate to ``true`` regardless
of content, use this with **store\_true** or **store\_false** as the
action.

.. code:: json

    {
      "hugetlb": false,
      "result": "PASS",
      ...
    }

any - True if any file returned a True result
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Like '**all**', but is ``true`` if any of the results evaluates to True.

.. code:: json

    {
      "hugetlb": true,
     "result": "PASS",
      ...
    }

list - Merge the file results into a single list
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For each result from each file, add them into a single list. **empty**
values are not added, but ``false`` is. If the result value is a list
already, then each of the values in the list is added.

.. code:: json

    {
      "hugetlb": ["HUGETLB_DEFAULT_PAGE_SIZE=2M", "HUGETLB_DEFAULT_PAGE_SIZE=4K"],
     "result": "PASS",
      ...
    }

fullname - Stores in a filename based dict.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The result from each file is still stored according to the *key*
attribute, but in a dictionary by the file's full name instead. This is
easier shown than explained:

.. code:: json

     "node1.out": {"hugetlb": null},
     "node2.out": {"hugetlb": "HUGETLB_DEFAULT_PAGE_SIZE=2M"},
     "node3.out": {"hugetlb": "HUGETLB_DEFAULT_PAGE_SIZE=4K"},
     "node4.out": {"hugetlb": null}
     "result": "PASS",

-  When using the **fullname** *per\_file* setting, the key cannot be
   ``result``.
-  The rest of the file's path is ignored, so there is potential for
   file name collisions, as the same filename could exist in multiple
   places.

name - Stores in a filename (without extension) based dict.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Just like **fullname**, but instead the file extension is removed from
filename when determine the key to store under. Only the last extension
is removed, so ``foo.bar.txt`` becomes ``foo.bar``.

.. code:: json

     "node1": {"hugetlb": null},
     "node2": {"hugetlb": "HUGETLB_DEFAULT_PAGE_SIZE=2M"},
     "node3": {"hugetlb": "HUGETLB_DEFAULT_PAGE_SIZE=4K"},
     "node4": {"hugetlb": null}
     "result": "PASS",

Errors
------

If an error occurs when parsing results that can be recovered from, a
description of the error is recorded under the ``error`` key. Each of
these is a dictionary with some useful values:

.. code:: yaml

    {
      ...
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

Included result parsers
-----------------------

Currently, Pavilion comes with 3 result parsers. \*
`constant <results/const.md>`__ \* `command <results/cmd.md>`__ \*
`regex <results/regex.md>`__
