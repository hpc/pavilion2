Installing Pavilion
===================

Installing Pavilion is mostly a matter of placing it's source somewhere,
providing it's (few) dependencies, and creating a pavilion.yaml config
file.

.. contents::

Requirements
------------

Pavilion has very few dependencies and requirements:

- Python 3.4 or newer
- A writeable space on a filesystem shared across all (tested) hosts in each cluster.

  - The path to this directory must be consistent across all cluster hosts.
  - It must support atomic file creation and appends of < 4kb.
- Lmod or 'environment modules' is recommended.

Filesystems
~~~~~~~~~~~

Pavilion works by recursively running itself in different modes at
different points in the testing process. This means certain paths, like
the Pavilion **root directory**, **working directory**, and used
**config directories** must have paths that are consistent across the
nodes and front-ends of any given system.

Pavilion places all builds, test working spaces, and lockfiles in a
**working directory** specified in the pavilion configuration (defaults
to ``~/.pavilion/``).

- Atomic (O\_EXCL) file creation is needed here for the creation of lock files.
- Atomic small appends are needed for writing to the status file. Not having
  this has a small chance of resulting in corrupted test status files.
- Both of these requirements are probably already satisfied by one or more of
  your cluster NFS partitions. Lustre filesystems are not recommended, mostly
  due to the type of load Pavilion presents to these.

Result Log
~~~~~~~~~~

The result log can be configured to write to an arbitrary filesystem.
That filesystem should be shared and have consistent paths as well, as
the log is written as the final on-node step in tests.

Recommended Directory Structure
-------------------------------

We recommend the following directory structure for Pavilion.

- ``<root>/pavilion/src`` - Clone/install pavilion here.
- ``<root>/pavilion/config`` - Your pavilion configuration files. See
  '`configuring pavilion <config.html>`__'.
- ``<root>/pavilion/working_dir`` - Where test runs and builds will be written.

The ``<root>/pavilion/config`` directory will contain all of your site
specific tests, plugins, and test source files. If you organize your tests in
separate repositories, you may check them out here, and simply link the
appropriate files into ``config/tests`` and ``config/test_src``.
Alternatively, you can make the entire config directory, source tarballs and
all, its own repository.

Install
-------

Pavilion installs are meant to be dropped into place as a complete
directory that contains the source and any
`dependencies <#dependencies>`__ missing on your system. This generally
starts with a git pull of the latest release of Pavilion.

.. code:: bash

    $ git clone <pav_repo>
    $ git checkout <release_tag>

You can also simply download and extract the source.

Dependencies
------------

Pavilion has a few dependencies, and most aren't required. Pavilion was
designed and tested against fairly recent (as of 2019-05) versions of
these, but it's likely that older, system provided versions may work
just as well. Conversely, the latest version should be fine as well. The
supported and tests versions for each are recorded in ``requirements.txt``.

-  `yaml\_config <https://github.com/lanl/yaml_config>`__ **(required)**
   - Used to define the test and pavilion configurations.
-  `**yc\_yaml** <https://github.com/pflarr/yc_yaml>`__ **(required)** - A
   modified pyyaml used by yaml\_config.
-  `**yapsy** <http://yapsy.sourceforge.net/>`__ **(required)** - The basis
   for Pavilion's plugin architecture.
-  `requests <https://pypi.org/project/requests/2.7.0/>`__ - Used for
   automatic downloads of test source files. This feature is disabled in
   the absence of this library, and tests that use it will fail with an
   error. The remaining dependencies are needed by requests.
-  `chardet <https://pypi.org/project/chardet/>`__
-  `idna <https://github.com/kjd/idna>`__
-  `python-certifi <https://pypi.org/project/certifi/>`__
-  `urllib3 <https://urllib3.readthedocs.io/en/latest/>`__

Installing Dependencies
~~~~~~~~~~~~~~~~~~~~~~~

There are two methods for installing the dependencies, via sub-repos or
using PIP and virtual environments.

Sub-repos
^^^^^^^^^

The Pavilion repository comes with all of it's dependencies as
sub-repos. To download them in this manner, simply run:

.. code:: bash

    git submodule update --init

This clones each of the dependencies into lib/sub\_repos. A softlink in
lib for each of the dependencies is included in lib that points to the
correct sub-directory for each of these. If you would prefer to use the
system version of a particular dependency, simply delete the
corresponding softlink in your install.

pytz
''''

Pytz is special, in that it has to be built. The build process is
simple, and requires nothing more than make and gcc. While Pavilion
doesn't actually use the compiled components of pytz, the python
components are dynamically generated and required.

.. code:: bash

    pushd lib/sub_repos/pytz
    make build

The softlink in lib already points to the expected location of the built
pytz.

virtualenv and pip
^^^^^^^^^^^^^^^^^^

You can also build pavilion dependencies using virtualenv and pip. If
you're unfamiliar, virtualenv sets up a custom python environment that
uses your system python and it's libraries as a base. You can then use
the virtual env's PIP package manager to download any additional (or
just newer) libraries needed by an application. As long as you use the
/bin/python, you'll have access to those additional libs.

It comes with a couple of caveats:

#. You will have to activate the virtual environment before running
   Pavilion, and in Pavilion scheduled jobs using the pavilion.yaml
   'pre\_kickoff' option.
#. All tests will run under this environment. That could cause problems for
   tests that utilize python (especially python2.x).

.. code:: bash

    pushd /your/pavilion/install
    VENV_PATH=/your/virtualenv/path
    # Setup a virtual environment 
    virtualenv -p /usr/lib/python3 ${VENV_PATH}
    # Update pip, because older versions sometimes have issues.
    ${VENV_PATH}/bin/pip install --update pip
    # Install all the pavilion requirements. 
    ${VENV_PATH}/bin/pip install -f requirements.txt
    # This has to be run before pav will work.
    ${VENV_PATH}/bin/activate

Environment Modules
===================

Pavilion uses the ``module`` command to load modules for tests. It will work
with either lmod or the tcl based 'environment modules' systems. This is
generally only needed if your cluster/s have a complex software environment
that supports multiple compilers and conflicting builds of libraries.

It is assumed that the module environment is set up before you run Pavilion. If
you need to set up this environment separately on allocations, use the
'env_setup' option in the general Pavilion configuration to add the commands
to do so.







