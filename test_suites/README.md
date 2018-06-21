# test_suites

This directory contains the default test configuration as well as the preconfigured
test files that can be compiled to generate situation-specific tests.

This is the directory to which the PAV_CFG_ROOT environment variable should point.

## test_configs

Test configurations that can be used on their own.  The intended run command for these is

```bash
pav run_test_suite [testname]
```

## hosts

This directory contains the configuration files to specify the machine being used.  The
files also include values for the number of nodes and processors per node.  If a number
for these values is specified to be greater than those in these files, an error will be
thrown.

## modes

This directory contains the files to specify different modes for running tests.  Some
modes that can be selected are the account, reservation, or QOS under which to submit
the jobs to the slurm scheduler.  The partition on which the tests should be run can
also be specified.

## tests

This directory contains the files to specify the test to be run.  These files provide
the relevant information for running the tests including the source directories,
the number of nodes on which to run the tests, etc.
