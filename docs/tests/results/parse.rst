.. _tests.results.parse:

.. contents::

Result Parsers
==============

Result parsers are fairly simple in practice, yet contain a wide variety of
options to help you pull results from test output.

Base Options
------------

Result parser plugins define their own configuration options, but many options
are handled at a higher level. These options are available for every result
parser, though some don't allow for any settings other than the default.

`for_lines_matching`_
  A regular expression that tells Pavilion which
  lines in the file should be examined with the result parser.

  **Default:** match every line.

`preceded_by`_
  A list of regular expressions used to match the series
  of lines before lines where we call the result parser.

  **Default:** No pre-conditions

`match_select`_
  When multiple lines match, which is the result?

  **Default:** Use the first matched result.

`files`_
  One or more filename globs (``*.txt``, ``test.out``) that selects which
  file to parse results from. These are relative to the test build directory
  (which is the working directory when the test runs).

  **Default:** '../run.log' (the run script output)

`per_file`_
  What to do with results from multiple files.

  **Default:** Keep the results from the first file with matches.

`action`_
  Manage the output type of the result parser.

  **Default:** Auto-convert to a numeric type, if possible.

Parsing Process
~~~~~~~~~~~~~~~

For each key in ``result_parse``, the results are parsed using the following
steps.

1. A list of files is generated from the globs in the ``files`` option, in
   order.

   - If a glob matches no files, the glob is given a 'no matches' entry
     in our list of results per file.
2. Each file is searched using the the ``for_lines_matching`` *AND*
   ``preceded_by`` options. The result parser is called to look at
   any lines that match all of these conditions.

   - The parser can look at more than just the matched line.
3. The result parser returns matched data, or not.
4. The ``match_select`` option which result to return from the list of
   matches.
5. The matches for each file found are modified and stored according to the
   ``per_file`` result.
   - This generally involves type manipulation according to ``action``.
   - It may involve storing results in multiple keys (see below).
















.. _match_select:
.. _for_lines_matching:
.. _preceded_by:


The ``result_parse`` section of each test config lets us configure additional
result parsers that can pull data out of test output files. By default
each parser reads from the run log, which contains the stdout and stderr
from the run script and your test.

.. code:: yaml

    mytest:
      scheduler: raw
      run:
        cmds:
          - ping -c 10 google.com

      result_parse:
        # The results.parse section is comprised of configs for result parsers,
        # identified by name. Each parser can have a list of one or more
        # configs, each of which will parse a different result value from
        # the test output.
        result_parse:
          regex:
          # Each result parser can have multiple configs.
            # The value matched will be stored in this key
            loss:
              # This tells the regex parser what regular expression to use.
              # Single quotes are recommended, as they are literal in yaml.
              regex: '\d+% packet loss'

              # We're storing this value in the result key. If it's found
              # (and has a value of 'True', then the test will 'PASS'.
            result:
              regex: '10 received'
              # The action denotes how to handle the parser's data. In this case
              # a successful match will give a 'True' value.
              action: store_true

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


Result Keys
-----------

By default, the value found by the result parser is simply stored in the
result json under the given key. Key names can be alpha-numeric with
underscores.

Multiple Result Keys
~~~~~~~~~~~~~~~~~~~~

*(New in 2.3)*

Result parsers can produce a list of values, and you can assign them to
multiple keys all at once. This is most common with the 'split' and 'regex'
result parsers.

.. code-block:: yaml

    result_parse:
        regex:
            # When you use multiple groupings in a regex, the
            # matches are returned in a list.
            "speed, runtime, points":
                regex: 'results: ([0-9.]+) ([0-9.]+) (\d+)'

            "



Result Value Types
~~~~~~~~~~~~~~~~~~

Result parsers can return any sort of json compatible value. This can be
a string, number (int or float), boolean, or a complex structure that
includes lists and dictionaries. Pavilion, in handling result values,
groups these into a few internal categories.

- **empty** - An empty result is a json ``null``, or an empty list.
  Everything else is **non-empty**.
- **match** - A **match** is a **non-empty** result that is also not json
  ``false``.
- **false** - False is special, in that it is neither **empty** nor a **match**.

The *actions* and *per\_file* sections below work with these categories
when deciding how to handle result parser values.


Result Parser Defaults
~~~~~~~~~~~~~~~~~~~~~~

(New in 2.3)

So you're parsing out 300 different bits of information with the *regex*
parser, and they all use the same, non-default, settings:

.. code-block:: yaml

    result_parse:
        regex:
            normal_key:
                regex: 'normal_key: (\s*)'
            mykey1:
                regex: 'mykey: (\s*)'
                per_file: name
                files: *.out
            mykey2:
                regex: 'mykey: (\s*)'
                per_file: name
                files: *.out
            # etc...

You can use the '_default' key to set defaults for all keys under that
result parser. Be careful with keys that don't need your new defaults though:

.. code-block:: yaml
    result_parse:
        regex:
            # Note that there is no order to these keys.
            _default:
                per_file: name
                files: *.out
            normal_key:
                # You have to go back to the defaults here, unfortunately.
                regex: 'normal_key: (\s*)'
                per_file: first
                files: '../run.log'
            mykey1:
                regex: 'mykey: (\s*)'
            mykey2:
                regex: 'mykey: (\s*)'
            # etc...

.. _tests.results.actions:

Actions
~~~~~~~

We saw in the above example that we can use an *action* to change how
the results are stored. There are several additional *actions* that can
be selected:

-  **store** - *(Default, mostly)* Simply store the result parser's output.
-  **store\_true** - *(Default for 'result' key)* Store ``true`` if the result
   is a **match** (non-empty and not false).
-  **store\_false** - Stores ``true`` if the result is not a **match**.
-  **count** - Count the length of list matches, regardless of contents.
   Non-list matches are 1 if a match, 0 otherwise.

.. _tests.results.files:

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

        result_parse:
            regex:
              # The matched values will be stored under the 'huge_size' key,
              # but that will vary based on the 'per_file' value.
              huge_size:
                  regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
                  # Run the parser against all files that end in .out
                  files: '*.out'
                  per_file: # We'll demonstrate these settings below

.. _tests.results.per_file:

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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
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

    result_parse:
        regex:
          huge_size:
              regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
              files: '*.out'
              per_file: name_list

Stores a list of the names of the files that matched, minus extension. The
actual matched values aren't saved.

.. code:: json

    {
      "huge_size": ["node2", "node3"],
    }
