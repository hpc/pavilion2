.. _tests.permutations:

Test Permutations
=================

Permutations allow you to create a 'virtual' test for each permutation of
the values of one or more variables.

.. contents::

Overview
--------

The `permute_on` test attribute defines a list of variables to permute over.
These can come from any variable set, but they cannot be deferred variables.

.. code:: yaml

    permuted_test:
        permute_on: [msg, person, date]
        subtitle: "{{person}}-{{msg}}"

        variables:
          msg: ['hello', 'goodbye']
          person: ['Paul', 'Nick']
        run:
          cmds: 'echo "{{msg}} {{person}} - {{date}}"'

The above would result in four virtual tests, each one echoing a
different message.

- That's 2 *users* \* 2 *people* \* 1 *date*

   - ``echo "hello Paul - 07/14/19"``
   - ``echo "hello Nick - 07/14/19"``
   - ``echo "goodbye Paul - 07/14/19"``
   - ``echo "goodbye Nick - 07/14/19"``
- The tests are scheduled independently when using ``pav run``.
- The subtitle attribute allows for adding a permutation based value to
  the test name. If it is not defined, all permutations of a test will
  have identical names, making it difficult to tell them apart.

Limitations
-----------

-  You can't permute on 'sched' variables. They don't exist until after
   permutations are generated.
-  You can't permute on *Deferred* variables. They can only have one
   value, and we won't know what that is until right before the test
   runs.
-  No attempt is made to remove duplicate tests, so if you permute on a
   variable you don't use it will create some identical test runs.

Complex Variables in Permutations
---------------------------------

Complex variables are a useful way to group variables together in a
permutation.

.. code:: yaml

    mytest:
        permute_on: compiler
        variables:
          compiler:
            - {name: 'gcc',   mpi: 'openmpi',   cmd: 'mpicc',  openmp: '-fopenmp'}
            - {name: 'intel', mpi: 'intel-mpi', cmd: 'mpiicc', openmp: '-qopenmp'}

        subtitle: '{{compiler.name}}'

        build:
          # Will result in `mpiicc -qopenmp mysrc.c`
          cmds: '{{compiler.cmd}} {{compiler.openmp}} mysrc.c'
        ...

This would create two virtual tests, one built with gcc and one with
intel. - The ``subtitle`` test attribute lets us give each a specific
name. In this case ``mytest.gcc`` and ``mytest.intel``. - Note that
using a variable multiple times **never** creates additional
permutations.

Permutations vs Combinations
----------------------------

Are they 'permutations' or 'combinations'? These words have very specific
meaning in a mathematical sense, and our usage here can be a bit confusing.
We are *permuting* over the *combinations* of multiple sets, and in neither
case are we are we using the word in a purely combinatorial sense.
