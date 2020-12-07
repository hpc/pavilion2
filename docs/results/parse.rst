
.. _results.parse:

Result Parsers
==============

Result parsers are fairly simple in practice, yet contain a wide variety of
options to help you collect results from test output.

.. contents::

General Operations
------------------

To see what result parsers are available, run:

.. code-block:: bash

    $ pav show result_parsers

To see full documentation for one these:

.. code-block:: bash

    $ pav show result_parsers --doc regex

Base Option Overview
~~~~~~~~~~~~~~~~~~~~

Result parser plugins define their own configuration options, but many options
are handled at a higher level. These options are available for every result
parser, though some don't allow for any settings other than the default.

:ref:`for_lines_matching <results.parse.line_select>`
  A regular expression that tells Pavilion which
  lines in the file should be examined with the result parser.

  **Default:** match every line.

:ref:`preceded_by <results.parse.line_select>`
  A list of regular expressions used to match the series
  of lines before lines where we call the result parser.

  **Default:** No pre-conditions

:ref:`match_select <results.parse.match_select>`
  When multiple lines match, which is the result?

  **Default:** Use the first matched result.

:ref:`files <results.parse.files>`
  One or more filename globs (``*.txt``, ``test.out``) that selects which
  file to parse results from. These are relative to the test build directory
  (which is the working directory when the test runs).

  **Default:** '../run.log' (the run script output)

:ref:`per_file <results.parse.per_file>`
  What to do with results from multiple files.

  **Default:** Keep the results from the first file with matches.

:ref:`action <results.parse.action>`
  Manage the output type of the result parser.

  **Default:** Auto-convert to a numeric type, if possible.
  **Default (for the result key):** 'store_true'

Parsing Process
~~~~~~~~~~~~~~~

For each key in ``result_parse``, the results are parsed using the following
steps.

1. A list of files is generated from the globs in the ``files`` option, in
   order.

   - If a glob matches no files, the glob is given an '_unmatched_glob' entry
     in our list of results per file. These start with an underscore, so
     won't be in the final results, but will be evaluated when using
     'per_file: all' or 'per_file: any'.
2. Each file is searched using the the ``for_lines_matching`` *AND*
   ``preceded_by`` options. The result parser is called to look at
   any lines that match all of these conditions.

   - The parser can look at more than just the matched line. The file is reset
     such that we continue looking at lines starting at the line after the
     matched line, regardless of what the result parser does.
3. The result parser returns matched data, or not.
4. The ``match_select`` option which result to return from the list of
   matches.
5. The matches for each file found are modified and stored according to the
   ``per_file`` result.
   - This generally involves type manipulation according to ``action``.
   - It may involve storing results in multiple keys (see below).


.. _results.parse.keys:

Result Keys
~~~~~~~~~~~

By default, the value found by the result parser is simply stored in the
result json under the given key. Key names can be alpha-numeric with
underscores.

**Keys that begin with an underscore are temporary.**
They will not be present in the final results.

Multiple Result Keys
^^^^^^^^^^^^^^^^^^^^

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

        split:
            # You can use underscore as the key for values you want to discard.
            # If there are more values than keys, that's fine too (the extras
            # will be dropped).
            "_, speed2, boats":
                sep: ","
                # Our comma separated line is after this one.
                preceded_by: ['^Results2']

.. _result_value_types:

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

.. _results.parse.defaults:

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
                files: '*.out'
            mykey2:
                regex: 'mykey: (\s*)'
                per_file: name
                files: '*.out'
            # etc...

You can use the '_default' key to set defaults for all keys under that
result parser. Be careful with keys that don't need your new defaults though:

.. code-block:: yaml

    result_parse:
        regex:
            # Note that there is no order to these keys.
            _default:
                per_file: name
                files: '*.out'
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

.. _results.parse.line_select:

Preceded_By and For_Lines_Matching
----------------------------------

As mentioned above, these are used to select which lines to call the result
parser on. They are combined to form a 'sliding window' of regexes that are
applied, in order, to check that a sequence of lines matches each of them. The
result parser is then called on the line matching the 'for_lines_matching'
regex.

Given:

.. code-block:: yaml

    result_parse:
        regex:
            foo:
                preceded_by:
                    - '^a'
                    - '^b'
                for_lines_matching: '^flm'

and a file that looks like:

.. code-block:: text

    c
    a
    a
    b
    flm
    a
    b
    flm

We'll match like:

.. code-block:: text

    c       ^a   X |      |        |
    a              | ^a ✓ |        |
    a              | ^b X | ^a ✓   |
    b                     | ^b ✓   |
    flm                   | ^flm ✓ |
    a                              | ^a ✓
    b                              | ^b ✓
    flm                            | ^flm ✓

Resulting in the the result parser being called twice.

- We resume checking from the line after any positive selection.
- Since the default 'for_lines_matching' is ``''`` (which matches everything),
  and 'preceded_by' is empty, by default pavilion calls the result parser on
  every line.

.. _results.parse.match_select:

Match_Select
------------

Pavilion calls each result parser for every preceded_by/for_lines_matching
match found. Match select allows us to control which match to use.

This is typically the first one (which is default), in which case Pavilion
stops searching the file after a single successful match is found.

You can also give an integer index (counting from zero, or backwards from -1)
to select the Nth match. If the match at that index doesn't exist, an error
is noted. The keywords 'first', and 'last' also work.

The 'all' keywords causes the full list of matches to be returned, including
instances where the result parser returned nothing.

.. _results.parse.action:

Actions
~~~~~~~

Actions change how Pavilion stores the final result value in the results.

-  **store** - *(Default, mostly)* Store the auto-type converted result into
    the given key/s. Strings that look like ints/floats/True/False will become
    that native type.
-  **store\_str** - Don't auto-convert strings, just store them.
-  **store\_true** - *(Default for 'result' key)* Store ``true`` if the result
   is a **match** (non-empty and not false).
-  **store\_false** - Stores ``true`` if the result is not a **match**.
-  **count** - Count the length of list matches, regardless of contents.
   Non-list matches are 1 if a match, 0 otherwise.

Some 'per_file' settings bypass the action step, namely 'namelist', which
doesn't store the value at all. Others, like 'all', will apply the 'action'
before the 'all' calculation.

.. _results.parse.files:

Files
~~~~~

By default, each result parser reads through the test's ``run.log``
file. You can specify a different file, a file glob, or even multiple
file globs to match an assortment of files. The files are parsed in the
order given, though ordering for files matched by glob wildcards is
filesystem dependent.

Relative paths are relative to the test run's *build* directory, which is the
working directory when the run/build scripts are run.
If you need to reference the run log in addition to other files, it is
one directory up from there, in ``../run.log``.

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

.. _results.parse.per_file:

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

name - Stores in a filename based dict.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    result_parse:
        regex:
          huge_size:
              regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
              files: '*.out'
              per_file: name

Put the result under the key, but in a dictionary specific to that file. All
the file specific dictionaries are stored under the ``per_file`` key.

.. code:: json

    {
      "fn": {
        "node1": {"huge_size": null},
        "node2": {"huge_size": "2M"},
        "node3": {"huge_size": "4K"},
        "node4": {"huge_size": null}
      }
    }

- When using the **name** *per\_file* setting, the key cannot be
  ``result``.
- The final extension is removed from the filename.
- The names are normalized and made unique. Non alphanumeric characters are
  changed to underscores. Ex: 'node%3.foo.out' -> 'node_3_foo'.


name_list - Stores the name of the files that matched.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: yaml

    result_parse:
        regex:
          huge_size:
              regex: 'HUGETLB_DEFAULT_PAGE_SIZE=(.+)'
              files: '*.out'
              per_file: name_list

Stores a list of the names of the files that matched. The actual matched values
aren't saved. This also normalizes the names and removes the extension as with
'per_file: name'.

.. code:: json

    {
      "huge_size": ["node2", "node3"],
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
