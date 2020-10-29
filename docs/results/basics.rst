
.. _results.basics:
.. _results:

Test Results
============

Every successful test run generates a set of results in JSON. These are
saved with the test, but are also logged to a central ``results.log``
file that is formatted in a Splunk compatible manner.

This page offers top level documentation on the working of this system.
For an overview how to use all the features, see
:ref:`tutorials.extracting_results`.

.. contents::

Result Logs
-----------

There are three different result logs:

per-test-run results json
~~~~~~~~~~~~~~~~~~~~~~~~~

The result json is written to a file named ``results.json`` in the test run
directory. This is used to recall results from test runs.

per-test-run result log
~~~~~~~~~~~~~~~~~~~~~~~

This results log records every step of the results gathering process in great
detail. It is stored in each test run directory in ``results.log``, and is
available via the ``pav log results <test_id>`` command.

Pavilion-wide result log
~~~~~~~~~~~~~~~~~~~~~~~~

The general result log keeps a record of the results of every test run under
your instance of Pavilion. It's location is configured via the general
``pavilion.yaml`` config, but defaults to residing in the working directory.
It's format is designed to be easily read by Splunk and similar tools.

Gathering Results
-----------------

Result gathering steps:

1) Generate the base result field values.
2) Use result parser plugins to parse values from result files.
3) Use result evaluations to modify results or generate additional values.
4) Convert the 'result' key from True/False to 'PASS'/'FAIL'.

All results are stored in a json mapping that looks like this:

.. code-block:: json

    {"avg_speed": 3.7999,
     "command_test": "PASS",
     "created": "2020-07-06 15:28:08.528899",
     "duration": "0:00:06.130584",
     "finished": "2020-07-06 15:28:08.528617",
     "id": 16176,
     "job_id": "123",
     "name": "mytests.base",
     "pav_result_errors": [],
     "result": "PASS",
     "return_value": 0,
     "sched": {"avail_mem": "80445",
               "cpus": "36",
               "free_mem": "76261",
               "min_cpus": "36",
               "min_mem": "131933.144",
               "total_mem": "125821"},
     "started": "2020-07-06 15:28:02.398033",
     "sys_name": "pav-test",
     "per_file": {
        "node01": {"raw_speed": 33},
        "node03": {"raw_speed": 39},
        "node05": {"raw_speed": 42}
     }
     "user": "bob"}

- Most values are stored at the top level of the mapping.
- Most scheduler variables are included, to improve tracking of how exactly
  the test ran.
- ``pav_result_errors`` stores a list of errors encountered when gathering
  results.
- The 'per_file' section stores information gathered across multiple
  results files This can be used to
  gather separate per-node information in cases where you have an output file
  for each node when using result parsers.
- Average speed in this case is a value calculated from each of the node speeds
  using *result evaluations*.
- The ``flatten_results`` key in the pavilion.log file can be used to convert
  results with multiple ``per_file`` results into a corresponding number of
  separate log entries.


Basic Result Keys
~~~~~~~~~~~~~~~~~

These keys are present in the results for every test, whether the test
passed or failed. To see the latest list of base result values, run
``pav show result_base``. All of these keys, as well as 'result', are reserved.

.. code-block:: text

    $ pav show result_base
     Name              | Doc
    -------------------+-------------------------------------------------
     name              | The test run name
     id                | The test run id
     created           | When the test was created.
     started           | When the test run itself started.
     finished          | When the test run finished.
     duration          | Duration of the test run (finished - started)
     user              | The user that started the test.
     job_id            | The scheduler plugin's jobid for the test.
     sched             | Most of the scheduler variables.
     sys_name          | The system name '{{sys.sys_name}}'
     pav_result_errors | Errors from processing results.
     per_file          | Per filename results.
     return_value      | The return value of run.sh

All time fields are in ISO8601 format.

Additionally, the 'file' key is reserved.

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

The Test Result
~~~~~~~~~~~~~~~

The 'result' key denotes the final test result, and will always be
either '**PASS**', '**FAIL**' or '**ERROR**'.  **ERROR** in this case means
the test had a non-recoverable error when checking whether the test
passed or failed.

You can set the 'result' using either result parsers or result evaluations.
It must be set as a single True or False value.

- For result parsers, this means you should use an 'action' of 'store_true'
  (the default) or 'store_false' (See :ref:`results.parse.action`). You
  will also need to use a 'per_file' setting that produces a single value, like
  'first' or 'all' (See :ref:`results.per_file`).
- For result evaluations this simply means ensuring that the evaluation
  returns a boolean, typically by way of a comparison operator.

If you don't set the 'result' key yourself, Pavilion defaults to adding the
evaluation: ``result: 'return_value == 0'``. This is why, by default,
Pavilion test runs **PASS** if the run script returns 0.
