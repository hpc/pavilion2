Configuring Pavilion
====================

Pavilion is driven largely by configurations. This documentation page covers
the ``pavilion.yaml`` file, which sets global pavilion settings.

See `Test Configs <tests/basics.html>`__,
`Host Configs <tests/basics.html#host-configs>`__,
`Mode Configs <tests/basics.html#mode-configs>`__, and
`Plugins <plugins/basics.html>`__ for information on the other types of
pavilion configuration.

.. contents::

Config Directories
------------------

Pavilion looks for configs in the following hierarchy by default, and
uses the first one it finds.

-  The current directory
-  The user's home directory
-  The directory given via the ``PAV_CONFIG_DIR`` environment variable.
-  The Pavilion lib directory **(don't put configs here)**

Each config directory can (optionally) have any of the sub-directories
shown here.

.. figure:: imgs/config_dir.png
   :alt: Pavilion Config Directory

   Config Directory Layout

Pavilion.yaml
-------------

Pavilion looks for a ``pavilion.yaml`` in the default config hierarchy,
and uses the first one it finds.

It's ok to run pavilion without a config; the defaults should be good
enough in many cases.

Generating a pavilion.yaml template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pavilion can print template files, with documentation, for all of it's
config files. In this case, use the command ``pav show config --template``.
Since this file is self documenting, refer to it for more information about
each of the configuration settings.

Setting You Should Set
~~~~~~~~~~~~~~~~~~~~~~

While everything has a workable default, you'll probably want to set the
following.

working\_dir
^^^^^^^^^^^^

This determines where your test run information is stored. If you don't
set this, everyone will have a separate history in
``$HOME/.pavilion/working_dir``.

shared\_group
^^^^^^^^^^^^^

If you have a shared working directory, you need a shared group to share
those files. Pavilion will automatically write all files as this group.

result\_log
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
