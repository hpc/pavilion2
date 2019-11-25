Building Tests
==============

The ``build`` section of the pavilion config defines how a test should
be built . This documentation covers how that's accomplished, as well as
detailed information on the ``build`` config section itself.

.. contents:: Table of Contents

Build Config Keys
-----------------

The documentation for what various keys do is spread throughout this
document.

-  `source\_location <#source_location>`__
-  `source\_download\_name <#source_download_name>`__
-  `extra\_files <#extra_files>`__
-  `modules <#modules-list>`__
-  `env <#env-mapping>`__
-  `cmds <#cmds-list>`__
-  `specificity <#specificity>`__

Building
--------

A build in Pavilion can be as simple as copying a few files, or it may
require downloading software, setting up a build environment, patching,
configuring, and compiling some source. Every build follows the same
steps in Pavilion, though in many cases those steps may be 'empty'. In
addition, Pavilion reuses existing builds where possible, which allows
for skipping most of the build steps.

Finding Source Files
~~~~~~~~~~~~~~~~~~~~

There are two ways to specify source in Pavilion: Through the
``source_location`` attribute and the ``extra files`` attribute.

.. code:: yaml

    build_example:
        build:
          source_location: my_test_src.gz
          
        extra_files:
          - my_test_patch1.patch
          - my_test_patch2.patch

These files are simply found (and possibly downloaded) at this stage in
the build process. Extraction and copying occurs when we populate the
build directory.

source\_location
^^^^^^^^^^^^^^^^

This attribute provides a build with a base archive, url, directory, or
file to use as the source. Local files are looked for in all of the
configuration directories in the `typical order <../config.md>`__, and
the first found is used . How the extracted files are used depends on
the structure of the extracted files themselves.

Archives and Compression
''''''''''''''''''''''''

Pavilion supports archives (.tar), compressed archives (tar.gz), and
simply compressed files (.gz). Archives and compressed file formats are
detected via file-magic (like the Unix ``file`` command). The actual
file name and extensions are ignored.

The following formats are supported:

-  gzip, bzip2, and lzma/lzma2 (.xz) compressed files
-  Similarly compressed tar archives
-  Zip archives

If you don't want an archive automatically extracted, include it under
``extra_files``.

Non-archives
''''''''''''

Pavilion can also copy non-archive files and directories. In this case
the file/directory is simply copied recursively. As mentioned above, a
copied directory will be the build root, but a file will be copied into
the build root.

URL's
'''''

URL's can be provided as well, and are automatically downloaded into the
``<working_dir>/downloads`` directory. Files are periodically checked
for updates, and new versions are downloaded as necessary. Downloaded
files are then treated as an archive or regular file as above.

File downloads depend on the Python **requests** library
`dependency <../../INSTALL.md>`__ being installed.

source\_download\_name
^^^^^^^^^^^^^^^^^^^^^^

When downloading source, we by default use the last of the url path as
the filename, or a hash of the url if is no suitable name. This
parameter to overrides the default behavior with a pre-defined filename.

extra\_files
^^^^^^^^^^^^

This build attribute lets you copy additional files into the build
directory. This typically includes patches, external build/run scripts,
or archives that shouldn't be extracted.

Create a Build Script
---------------------

Most of the build config goes into automatically writing a build script.
This script is what sets up the build environment and then runs the
actual build. The script working directory is always the build
directory.

The script is composed in the following order: - module manipulation -
environment changes - commands

**Note that the build config (and thus script) can't contain `Deferred
Variables <variables.md#deferred-variables>`__.**

Not only do we need to know the value of everything to make the build
hash, but the build might not even run in a scheduled environment where
the deferred value is available.

An example config and build script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: yaml

    build-example:
        build:
          source_location: my_test.tar.gz
        
          modules: [gcc, openmpi]
          
          env: 
            # Add to the path.
            PATH: "${PATH}:$(which gcc)"
            # unset the USER environment variable.
            USER: 
            
          cmds:
            - ./configure
            - ./make

Would result in a script like:

.. code:: bash

    #!/bin/bash

    # This contains utility functions used in Pavilion scripts.
    source /home/bob/pavilion/bin/pav-lib.bash

    # Load the modules, and make sure they're loaded 
    module load gcc
    check_module_loaded gcc

    module load openmpi
    check_module_loaded openmpi

    # Set environment variables
    export PATH=${PATH}:$(which gcc)
    unset USER

    # Build the test.
    ./configure
    ./make

modules (list)
^^^^^^^^^^^^^^

Modules to ``module load`` (or swap/remove) from the environment using
your cluster's module system.

For each module listed, a relevant module command will be added to the
build script.

See `Module Environment <env.md#modules>`__ for more info.

env (mapping)
^^^^^^^^^^^^^

A mapping of environment variable names to values.

Each environment variable will be set (and exported) to the given value
in the build script. Null/empty values given will unset. In either case,
these are written into the script as bash commands, so values are free
to refer to other bash variables or contain sub-shell escapes.

See `Env Vars <env.md#environment-variables>`__ for more info.

cmds (list)
^^^^^^^^^^^

The list of commands to perform the build.

-  Each string in the list is put into the build script as a separate
   line.
-  The return value of the last command in this list will be the return
   value of the build script.

   -  The build script return value is one way to denote build success
      or failure.

-  If your script failures don't cascade (a failed ``./configure``
   doesn't result in a failed ``make``, etc), append ``|| exit 1`` to
   your commands as needed. You can also use ``set -e`` to exit on any
   failure.

Generate a Build Hash
~~~~~~~~~~~~~~~~~~~~~

Pavilion uniquely identifies each build by generating a hash based on
the build source and build script. If a build directory with that build
hash exists, then Pavilion simply uses that existing build.

The build hash is composed from:

1) The build script.
#) The build's ``specificity``.
#) The source file or archive gotten using ``source_location``.

   a) Source directories are scanned for changes, rather than recursive hashed.
      The most recent mtime of the directory is hashed.

#) Each of the ``extra_files``.

specificity
^^^^^^^^^^^

Use this field to add additional criteria to the build hash. For
instance, if you'd like your builds to be host specific, you could set
this to ``"{{sys.sys_host}}"``.

Locking the Build
~~~~~~~~~~~~~~~~~

The rest of the build process occurs under the auspices of a lockfile.
This allows the build directory creation, population, and build to occur
without conflicts from other tests that might be trying to create the
same build. This is true even if those tests are running on different
nodes or even entirely different hosts, assuming they all share a
working directory on a shared file system.

-  If the build directory exists, then the build is ready. The test can
   simply continue without building.
-  The initial build directory is a temp file that is atomically moved
   into place. There should never be a point where a partial build
   exists.
-  The build script is expected to periodically produce output,
   otherwise Pavilion will assume it deadlocked or otherwise failed and
   release the lock.

Create and Populate a Build Directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The construction of the build directory is closely tied to the structure
of the extracted contents of the file/directory . These are generally
extracted/copied directly into their final location (once they've been
downloaded). The ``extra_files`` are then copied into that directory.

There are three basic cases.

No source
^^^^^^^^^

An empty source directory is created.

Single Directory
^^^^^^^^^^^^^^^^

If the file (or extracted archive) is a single directory, that directory
becomes the build directory.

.. code:: bash

    # This tar file has a single top-level directory. 
    # The 'src' directory will be the build directory.
    tar -tf src.tar.gz
      src/README.txt
      src/mytest.c
      
    ls build_dir
      README
      mytest.c

File/s
^^^^^^

In all other cases, the build directory will simply contain the files.

.. code:: bash

    # This tar file has multiple files at the top level.
    # The build directory will contain these files.
    tar -tf src2.tar.gz
      README.txt
      src/mytest.c
      
    ls build_dir
      README.txt
      src/mytest.c 

Perform the Build
~~~~~~~~~~~~~~~~~

Once the build directory is set up, we can run the build itself.

-  The build can be run either on nodes right before the test runs, or
   on the kickoff host, depending on the value of ``on_nodes``.

   -  Default is to build on the test allocation.
   -  Building on the kickoff host means you find problems really early.

-  To build, pavilion just runs the build script.

   -  The working directory is the build directory.

-  The build is considered successful if the build script exits
   successfully.
-  All regular files in the build directory are given read-only
   permissions.

on\_nodes
^^^^^^^^^

If true (default is false), build the test on an allocation right before the
test is run. Otherwise, build before kicking of the test on the kickoff host.
It's assumed that the kickoff host has an environment (and module
system) comparable to a node.

Copy the Build
~~~~~~~~~~~~~~

Whether a test performs the build or just uses an existing build, each
test needs a copy of the build to run. Instead of actually duplicating
the build, Pavilion creates an identical directory structure with
symlinks to each of the regular files in the build, a **symlink** copy.

.. figure:: ../imgs/working_dir.png
   :alt: Build Symlinks

   build symlinks

Multiple tests can thus use the same build files, delete build files,
and write new files to the build directory without concern for other
tests. **Tests cannot append or alter the build files.** If a test needs
to alter a file, the symlink should be deleted and replaced with a copy
of the real file as part of the test run commands.
