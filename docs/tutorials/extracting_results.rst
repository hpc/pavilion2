
.. _tutorials.extracting_results:

Extracting Results Tutorial
===========================

This tutorial is meant to teach you how to parse a variety of results from
your test output. For a full accounting of all the features of result
parsers and evaluations, see :ref:`results`.

For every test run under Pavilion that completes, a result JSON 'mapping' is
created with keys and values that describe the run. Pavilion provides a lot of
information by default. Try ``pav show result_base`` to see a list and
description of those keys. We'll be adding to that by parsing values from files
and then doing some math.

.. contents::

Setup
-----

.. code-block:: bash

    # Set up the tutorial environment
    # (sets PAV_CONFIG_DIR to examples/tutorials and adds Pavilion to PATH)
    $ source examples/tutorials/activate.sh

    # You should be able to see our example test.
    $ pav show tests

    # You should be able to run it, and look at the results.
    $ pav run extract_tut
    $ pav results -f last


The test itself is in ``examples/tutorials/extract_tut.yaml``.
Over the course of this tutorial, we'll be expanding this file to parse
all of the results produced by this test.

Debugging
---------

You're going to do things wrong from time to time, and Pavilion provides some
help with debugging.

1. Check the 'pav_result_error' key in the results. It has information about
   what might have gone wrong during parsing.
2. Check the result gathering log: `pav log result <test_id>` It tracks what
   happens during the result gathering step closely.
3. You don't have to re-run a test to alter its result gathering. For an
   existing test run, just use the '--re-run' option. This will use the current
   test config to re-run the result gathering step, and report the new results
   accordingly (it doesn't save them, just prints them).

Some Test Output
----------------

In our case, it's two types of files. First is the output of the
'run.sh' script Pavilion created from our run section, which looks like this:

.. code-block:: text

    Welcome to our contrived example!

    Ran for: 36.52s
    GFlops: 9003

    Settings (weebles, wobbles, marks, conflagurated?)
    - - - - - - - - - - - - - - - - - - - - -
    32, 98.5, 18.5, True

      N-dim     |   Elasticity   |  Cubism
    -----------------------------------------
     1          | 45.2           | 16
     2          | 25.9           | 121
     4          | 35.1           | 144

    That went terribly.

Use ``pav status`` to find your test's id, and then run
``pav log run <test_id>`` to see this for yourself.

In addition, the test produced per-node output files. These are named
``<node_name>.out`` (ie 'node0045.out'), and look like this inside:

.. code-block::

    Node 5 reporting sir!
    Parameters are optimal!
    Firing on all cylinders!

    0-60 in 42.3s
    Single node flops are 32.5123 bunnies.

    Confusion is setting in.
    Good night!

You can view these with ``pav cat <test_id> build/node5.out``.

**TASK:** Run the test and view the run log and one of the node output files.

Basic Regex Parsing
-------------------

There's a lot to parse here.

Let's start with the run time. Pavilion already gives a test duration, but
the test provided number is probably more accurate.

.. code-block:: yaml

    example:
        # This is a figurative ellipsis.
        ...

        # Result parser configs go here.
        result_parse:
            # Each result parser type has it's own subsection. We're using
            # the regex parser, so:
            regex:
                # Now we add the key we're going to store to, and the config
                # to pull out that values.
                run_time:
                    # By default Pavilion applies the result parser to every line
                    # in the file, until it finds a match. That works here.
                    # We'll define a regular expression with a matching group;
                    # a section in parenthesis that the regex will capture.
                    # That captured value will be the value stored.
                    regex: 'Ran for: (\d+\.\d+)s'

**NOTE: Always put your regexes in single quotes.** It prevents YAML from
processing escapes like '\d'. In double quotes that regex would have to be
``"Ran for: (\\d+\\.\\d+)s"``. Yuck!

The results would look like this (plus the rest of the default fields).

.. code-block:: json

    {
        "name": "results_tut.example",
        "id": 32,
        "run_time": 32.5,
    }

Note that the value is automatically converted to a floating point number,
simply because it looks like one.

**TASK**

- Add the run_time result parser to res_tutorial.yaml, run it, and check out
  the results.
- Look at the documentation for the 'regex' parser, with
  `pav show result_parser --doc regex`. We'll be looking at the rest of the
  general options in this tutorial.

Evaluations
-----------

Let's parse out the gflops similarly. We don't want GigaFlops though, we want
PetaFlops, so let's convert it.

Assign it to the ``_gflops`` key.

**Temp Keys**: Keys that start with underscore, including just an underscore,
are temporary and won't be in the results!

.. code-block:: yaml

    example:
        ...

        result_parse:
            regex:
                run_time:
                    regex: 'Ran for: (\d+\.\d+)s'
                _gflops:
                    regex: 'GFlops: (\d+)'

        # The 'result_evaluate' section lets us perform math. The syntax is
        # the same the inside of '{{  }}' sections in Pavilion strings,
        # but the *variables* are result keys! So we can reference '_gflops'
        # here.
        result_evaluate:
            tflops: 'gflops/1000'
            pflops: 'tflops/1000'

- Result 'evaluate' keys will be stored in the results JSON mapping
- You can reference other 'evaluated' keys. Order doesn't matter.

**TASK**

Add the '_gflops' and 'tflops' keys to your results, and test it all out.
Notice that '_gflops' won't be in your results!.

Line Selection and Multiple Keys
--------------------------------

Our examples so far were able to find the right line because our regexes are
able to do some of that matching inherently. For other result parsers, we
need to tell Pavilion what lines we're looking for. We can do this with the
options 'for_lines_matching', 'preceded_by', and 'match_select'.

The 'for_lines_matching' option is a regex that must match a given line for
it to be parsed by the result parser.

The 'match_select' option let's you pick which match to use if multiple lines
successfully parse out a value. Pavilion uses the first match by default (and
doesn't even look for more, but you can get 'all', 'last', or specify an
integer to pull out a specific one (Counting from zero, or backwards from -1).

The 'preceded_by' option is a list of regexes that must match the lines that
precede the line we're looking for, one-to-one. Let's use it to find the
'Settings' in our results.

.. code-block:: yaml

    example:
        ...

        result_parse:
            ...
            # The 'split' parser splits a line by some separator, and
            # returns a list of the parts (all stripped of whitespace).
            split:
                settings:
                    preceded_by:
                        - '^Settings'  # Match the 'Settings (weebles,' line
                        - '^- - - ' # THEN those weird dashes.
                        # The parser will parse the line after these.
                    # These are comma separated.
                    sep: ','

That should work as is, and store a list of the split values (type converted)
under the 'settings' key. Note that the weird dashes occur twice in the file,
which is why we have to check for both it and the line before it.

**TASK**: Verify that we get the 'settings' key in the results.

But we probably don't want a list, we want these values stored under a
reasonably named key. Let's make that happen:

.. code-block::

    example:
        ...
        result_parse:
            ...
            split:
                # We can list multiple values as the 'key'.
                "weebles, _, marks":
                    preceded_by:
                        - '^Settings'  # Match the 'Settings (weebles,' line
                        - '^- - - ' # Then those weird dashes.
                    # These are comma separated.
                    sep: ','

**TASK**: Try that, and look at the results.

We should now have 'weebles', and 'marks' stored, but what
happened to 'wobbles' (the second item) and 'conflagurated'?
We tossed 'wobbles' by storing it in '_', which you can do as many times as
needed. You also don't have to provide a key for every item in the list,
those will be ignored too.

Parsing Whole Tables
--------------------

The 'table' parser does what it's named for, with some (hopefully rare)
caveats. We need to tell it where to find the table, and a few other bits of
information, and we're good to go. Let's use it to parse the 'N-dim' table in
our results.

.. code-block:: yaml

    example:
        ...

        result_parse:
            ...

            table:
                dim_results:
                    # Identify the table by the heading row.
                    # We'll use it to get our column names.
                    for_lines_matching: '^N-dim'

                    # The column delimiter is a pipe, which we need to escape
                    # because it has special meaning in re's
                    delimiter_re: '\|'

That gets me:

.. code-block:: json

    {
     "dim_results": {"1": {"cubism": 16, "elasticity": 45.234},
                     "2": {"cubism": 121, "elasticity": 25.9},
                     "4": {"cubism": 144, "elasticity": 35.11}},
     "duration": 0.032327,
    }

- The first column becomes the row name. You can turn that off.
- The header row defines the column names, but you can give them too.
- The line of dashes gets removed automatically (also customizable).
- See `pav show result_parsers --doc table` for more options.

Now, the caveats:

- Missing data items are fine, as long as the columns aren't whitespace
  delimited.
- Spaces in data or column names also causes problems in whitespace delimited
  tables.
- So, be careful with whitespace based tables.

**TASK:** Add parsing of the n-dim table to your results.

Actions and Setting the 'result' Key
------------------------------------

The action option modifies your results. The default action ('store')
does the automatic type conversion, and there are a variety of others too.
Let's use actions to set the overall result of our test.

We do this by setting the 'result' key. It has to be set to a boolean,
whether we set it through a result parser or an evaluation expression.
Our example test will print one of several messages at the end, but
only 'That went terribly' is a failure. We'll use the action 'store_false'
to set 'result' to false only if we find that message in the results.

.. code-block:: yaml

    example:
        ...

        result_parse
            regex:
                result:
                    # If we find a match, store False instead of the match.
                    action: store_false
                    regex: 'That went terribly'

- if we were looking for a particular message to denote success rather than
  failure, then we wouldn't have to set 'action' at all. While 'store' is the
  normal default, 'store_true' is the default for the 'result' key.
- If you see a result of 'ERROR' instead of 'PASS' or 'FAIL' it probably
  means you somehow succeeded in assigning a non-boolean to 'result'. Don't
  do that.

**TASK**: Our the example test will randomly print one of several messages. Add
this result parser to your config, and run the test mulitple times until you
see both a 'PASS' and a 'FAIL' result.

Parsing Multiple Files
----------------------

You may have noticed the 'files' key in the general options for result
parsers. Not only can you specify a different file than the default (the run
log at '../run.log'), you can give multiple file globs to parse data from a
bunch of files at once. These are looked for in the test run's ``build/``
directory, which is the working directory when a test runs.

By default Pavilion just uses the result from the first file with a result. It
can do a variety of other things by using the 'per_file' option, such as
make a list of all files with a match, or build a mapping of results from
each file. We'll use this second option now.

**TASK:** Use ``pav cat <test_id> build/node1.out`` to review a per-node output
file.

.. code-block:: yaml

    example:
        ...
        result_parse:
            regex:
                flops:
                    regex: '(\d+\.\d+) bunnies$'
                    # Parse every file that matches '*.out'. It works just
                    # like it would on the command line.
                    files: '*.out'
                    # Put these in a dictionary by the filename (minus the
                    # extension, and normalized a bit).
                    per_file: 'name'

Would get results that look like:

.. code-block:: json

    {
     "per_file": {"node1": {"flops": 34.89},
                  "node2": {"flops": 37.2},
                  "node3": {"flops": 39.49},
                  "node4": {"flops": 139.72},
                  "node5": {"flops": 31.67}},
     "result": "PASS",
     "return_value": 0,
    }

**TASK:** Add a parser for the 'accel' data in the per-node results.

Wildcard Evaluations
--------------------

What if we want the average flops across all the nodes? How about finding
outliers? We can use the 'result_evaluate' section and functions to do that.

First, we need a function to handle this. Pavilion provides both an 'avg'
function and 'outliers' function to handle these tasks. If you need a
function that Pavilion doesn't already provide, they're easy to add through
the :ref:`plugins.expression_functions` system. Note that these functions are
available both in the 'result_evaluate' section, and in '{{ }}' expressions in
other Pavilion test config strings.

**TASK:** Use ``pav show functions`` to see a list of functions, and what
arguments they take.

We can access individual values deep in the results like this:
``per_file.node1.flops``. We can get a list of the node files found using
the 'keys()' function on 'per_file': ``keys(per_file)``.

Most importantly, get the average flops we'll need a list of them for each
node. You can do this with a wildcard (``*``) where the node name goes.
``per_file.*.flops``  Let's use this to calculate the average flops, and
find any outliers.

.. code-block:: yaml

    example:
        ...

        result_parse:
            regex:
                flops:
                    regex: '(\d+\.\d+) bunnies$'
                    files: '*.out'
                    per_file: 'name'

        result_evaluate:
            # Get the average flops, given the flops value from each of our
            # node results files.
            avg_flops: 'avg(per_file.*.flops)'
            # The outliers function takes a list of values, a corresponding
            # list of names to associate with those values, and a number of
            # standard deviations from the mean to consider 'normal'.
            # It returns a mapping of 'name: stdev_from_mean' for items
            # that exceed that limit.
            # The first and second lists are guaranteed to be in corresponding
            # order.
            _outliers: 'outliers(per_file.*.flops, keys(per_file), 1.3)'
            # Extract just the list of outlier names.
            outliers: 'keys(_outliers)'

**TASK:** Add these evaluations to your config and test them.

Constants
---------

Sometimes the value you need to add to the results is already in a Pavilion
variable, or is simply a constant. We can add those to our results using
the 'result_evaluate' section.

As discussed in :ref:`tests.values.expressions`, you can add expressions to
almost any Pavilion value string, including 'result_evaluate'. These are
resolved before results are processed, altering the *configuration* strings
before they are processed for result evaluations. The result of that is
always a string, which is then evaluated as a 'result_evaluate' expression,
which can produce a variety of types.

This can be useful for simply adding constants, either as a whole result
values or as a constant in a calculation. You should, however, be wary of
they types you're inserting. Let's walk through an example:

.. code-block:: yaml

    bad_evals:
        variables:
            answer: 42
            answer2: 'Forty-Two'

        result_evaluate:
            # This is ok, because 42 looks like a number.
            answer: '{{answer}}'
            # This needs to be in quotes, though.
            message: 'The answer is {{answer2}}'
            # better
            message2: '"The answer is {{answer2}}"'


This would result in an error because 'message' isn't a valid expression. The
error wouldn't show up until we gather the test run's results. The
substitutions for 'answer' and 'answer2' would happen when we resolve the test
configuration, giving us a test that looks like this:

.. code-block:: yaml

    bad_evals:
        result_evaluate:
            # This is fine, and the 'answer' result key will be the integer 42.
            answer: '42'
            # This is not a valid expression.
            message: 'The answer is Forty-Two'
            # Instead, it should be in double quotes to evaluate to a string.
            message2: '"The answer is Forty-Two"'

**TASK**:

- Add 'baseline' pavilion variable to your config under 'variables' set to 23.
- Then use it to produce an 'adj_tflops' result values, which should be the
  extracted tflops value divided by that baseline.

.. _github: https://github.com/hpc/pavilion2

Conclusion
----------

The Pavilion results system has a lot of powerful options and features, but
remains fairly simple to use in most cases. If you run into any issues,
feel free to file as tickets them on the Pavilion2 `github`_.