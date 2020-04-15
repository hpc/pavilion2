Logging
=======

.. contents:: Table of Contents

Cross-Process Logging
---------------------

.. autoclass:: pavilion.log_setup.LockFileRotatingFileHandler
    :members: __init__, emit, handleError, _should_rollover, _do_rollover
    :undoc-members:
    :show-inheritance:

Logger Setup
------------

.. autofunction:: pavilion.log_setup.record_factory

.. autofunction:: pavilion.log_setup.setup_loggers
