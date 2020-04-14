Utilities
=========

.. contents:: Table of Contents

Command Output
--------------

.. autofunction:: pavilion.output.fprint
.. autofunction:: pavilion.output.draw_table
.. autofunction:: pavilion.output.dbg_print

Colorized Output
~~~~~~~~~~~~~~~~
Both ``fprint()`` and ``dbg_print`` above take a 'color' argument, which
allows you to colorize the output.

.. autodata:: pavilion.output.COLORS
    :annotation:
.. autoclass:: pavilion.output.ANSIString
    :members:

JSON Output
~~~~~~~~~~~
.. autofunction:: pavilion.output.json_dump
