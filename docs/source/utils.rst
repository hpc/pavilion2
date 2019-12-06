Utilities
=========

.. automodule:: pavilion.utils

.. contents:: Table of Contents

Command Output
--------------

.. autofunction:: pavilion.utils.fprint
.. autofunction:: pavilion.utils.draw_table
.. autofunction:: pavilion.utils.dbg_print

Colorized Output
~~~~~~~~~~~~~~~~
Both ``fprint()`` and ``dbg_print`` above take a 'color' argument, which
allows you to colorize the output.

.. autodata:: pavilion.utils.COLORS
    :annotation:
.. autoclass:: pavilion.utils.ANSIString
    :members:

JSON Output
~~~~~~~~~~~
.. autofunction:: pavilion.utils.json_dump
.. autofunction:: pavilion.utils.json_dump

File Handling
-------------
.. autofunction:: pavilion.utils.flat_walk
.. autofunction:: pavilion.utils.get_mime_type

OS Operations
-------------
.. autofunction:: pavilion.utils.get_login

