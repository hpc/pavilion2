.. _plugins.result_loggers:

Result Logger Plugins
=====================

Result logger plugins allow users to customize how test results are logged. These plugins can not
only be used to control what files results are logged to, but can also delegate logging to external
services. Pavilion has two built-in result logging plugins: common file loggers and series
file loggers.

Configuring Result Loggers
--------------------------

Result loggers can be specified in the Pavilion configuration file, ``pavilion.yaml``, under the
``result_loggers`` key. This key takes a list of dictionaries, each of which specifies a single
logger. While the specific set of keys varies by plugin, all plugins take at minimum a ``plugin``
key, whose value is the name of the plugin.

Common File Loggers
-------------------

The common file logger is the simplest possible result logger. It logs all test results to a single
log file, located in a specified location. Note that common file loggers rely on locking mechanisms
that require atomic file creation, which may not be present on all filesystems.

The format for configuring a common file logger consists of the plugin type (``common_file``) and
the destination of the log file:

.. code-block:: yaml
  result_loggers:
    - plugin: common_file
      dest: /path/to/results.log

Series File Loggers
-------------------

Series file loggers log to a separate log file for each test series. This can be advantageous
because it provides a lock-free alternative to writing to a single common log file, which
eliminates lock contention. Individual series logs can then optionally be aggregated by a service
such as Splunk.

Like the common file logger, the configuration for a series file logger takes a ``dest`` key, but
unlike the common file logger, it expects a directory instead of a file. Series logs are placed
under this directory and named according to ``<series ID>.log``:

.. code-block:: yaml
  result_loggers:
    - plugin: series_file
      dest: /path/to/directory/

Using Multiple Loggers
----------------------

It is possible to configure multiple simultaneous loggers, including multiple instances of the
same logger type:

.. code-block:: yaml
  result_loggers:
    - plugin: series_file
      dest: /path/to/directory/
    - plugin: series_file
      dest: /path/to/another/directory/
    - plugin: common_file
      dest: /path/to/results.log
