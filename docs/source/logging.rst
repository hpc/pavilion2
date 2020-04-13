Logging
=======

.. contents:: Table of Contents

Cross-Process Logging
---------------------

.. autoclass:: pavilion.logging.LockFileRotatingFileHandler
    :members: __init__, emit, handleError, _should_rollover, _do_rollover
    :undoc-members:
    :show-inheritance:

Logger Setup
------------

.. autofunction:: pavilion.logging.record_factory

.. autofunction:: pavilion.logging.setup_loggers
