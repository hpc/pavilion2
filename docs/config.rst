.. _config:

Configuring Pavilion
====================

Pavilion is driven largely by configurations. This documentation page covers
the ``pavilion.yaml`` file, which sets global pavilion settings.

See :ref:`tests.format` for information on the other types of
pavilion configuration.

.. contents::

.. _config.config_dirs:

Config Directories
------------------

Pavilion looks its main ``pavilion.yaml`` config in the following hierarchy
and uses the first one it finds.

-  The user's `~/.pavilion` directory.
-  The directory given via the ``PAV_CONFIG_DIR`` environment variable.
-  The Pavilion lib directory **(don't put configs here)**

The pavilion.yaml file can configure additional locations to look for test,
mode, and host configs, as well as plugins using the ``config_dirs`` option.
The ``~/.pavilion`` directory is only searched for ``pavilion.yaml`` by
default, but searches for other configs there can be turned on in ``pavilion
.yaml``

Each config directory can (optionally) have any of the sub-directories
shown here.

.. figure:: imgs/config_dir.png
   :alt: Pavilion Config Directory

   Config Directory Layout

It's ok to run pavilion without a ``pavilion.yaml``; the defaults should
be good enough in many cases.

Generating a pavilion.yaml template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pavilion can print template files, with documentation, for all of it's
config files. In this case, use the command ``pav show config --template``.
Since this file is self documenting, refer to
it for more information about each of the configuration settings.

Setting You Should Set
~~~~~~~~~~~~~~~~~~~~~~

While everything has a workable default, you'll probably want to set the
following.

.. _config.working_dir:

working_dir
^^^^^^^^^^^

This determines where your test run information is stored. If you don't
set this, everyone will have a separate history in
``$HOME/.pavilion/working_dir``.

shared_group
^^^^^^^^^^^^^

If you have a shared working directory for multiple users, you need a shared
group to share those files. Pavilion will automatically write all files as
this group.

result_log
^^^^^^^^^^^

The result log holds all the result json for every test you run. If you
want to feed that into splunk, you may want to specify where to write
it.

proxies
^^^^^^^

Pavilion can auto-download and update source for tests, but it needs to
be able to get to the internet.

.. code:: yaml

    proxies:
        http: myproxy.example.com:8080
        https: myproxy.example.com: 8080

    no_proxy:
      - example.com
      - alsolocal.com
