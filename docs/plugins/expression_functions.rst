.. _plugins.expression_functions:

Expression Function Plugins
===========================

Expression Function plugins are what provide the implementation for all
functions in Pavilion string expressions.

.. code-block:: yaml

    mytest:
        run:
            env:
                TASKS: "{{ max([5, sched.min_ppn]) }}"

The ``max()`` function takes a list of numbers, and returns the largest. That
value will be assigned to the ``TASKS`` environment variable.

In this tutorial, we'll show you how to add a new function to Pavilion for
use in your tests' expressions.

.. contents::

Needed Files
------------

Expression Function plugins are just like every other Pavilion plugin. See
:ref:`plugins.basics` for instructions on setting up the basic files.

The Plugin Base Class
---------------------

Your plugin module file will need to contain the class definition for your
plugin.

.. code-block:: python

    from pavilion import expression_functions

    # All function plugins inherit from the 'FunctionPlugin' class
    class Max(expression_functions.FunctionPlugin):

        # As with other plugin types, we override __init__ to provide the
        # basic information on our plugin.
        def __init__(self):

            super().__init__(
                # The name of our plugin and function
                name="max",

                # The short description shown when listing these plugins.
                description="Get the max of a list of numbers",

                # The arg_specs define how to auto-convert arguments to the
                # appropriate types. More on that below.
                # Note: (foo,) is a single item tuple containing foo.
                arg_specs=([num],)
            )

        # This method is the 'function' this plugin defines. It should take
        # arguments as defined by the arg_spec. It should also return one of the
        # types understood by Pavilion expressions (int, float, bool, string, or
        # lists/dicts containing only those types).
        @staticmethod
        def max(nums):
            """The docstring of the function will serve as its long
            documentation."""

            # We don't need to do any type checking, those conversions
            # will already be done for us (and will raise the appropriate
            # errors).
            return max(nums)

Arg Specs
---------

The ``arg_specs`` tell Pavilion what types to expect for each argument of the
function, and how to handle type autoconversion. This is necessary because we
will often have numbers as strings in variable values that will need to be
converted to a numerical type.

Basic Types
~~~~~~~~~~~

Items in the ``arg_specs`` can be a type conversion function to auto-convert
a value into the type needed by the function. This typically means using one of
``float()``, ``str()``, ``int()``::

    # This list of arg_specs denote that the function should expect
    # three arguments: a float, a string, and an int.
    arg_specs=(float, str, int)


The Num Type
^^^^^^^^^^^^

If your function can take any numerical value, use
the ``num`` function as we did above in our ``Max``. This will convert the
given value to an int, float or bool, according to what the input (or input
string) most closely resembles. It also handles 'True' and 'False' strings as
boolean values::

    >>> from pavilion.expression_functions import num
    >>> num("7")
    7
    >>> num("7.0")
    7.0
    >>> num("False")
    False

Depending on the function, you may also want to take care to maintain and
return the original type.

Lists and Dicts
~~~~~~~~~~~~~~~

Function plugin arguments can also be any structure of lists and dicts as long
as the final contained values are one of the basic types listed above.

For lists, simply give a list with the expected type as the only item.::

    # The function expects two arguments, a list of ints and a list of strings.
    arg_specs=([int], [str])

Similarly for dicts, include the expected keys in a dictionary and the
expected type functions as the values. Only keys listed will be visible
to the function.::

    # The function expects a dict with 'host' (str) and 'speed' (float) keys.
    arg_specs=({'host': str, 'speed': float}, )

More usefully, you can combine lists and dicts.::

    # The function expects a list of host/speed dicts
    arg_specs([{'host': str, 'speed': float}],)

Overriding Arg Specs
~~~~~~~~~~~~~~~~~~~~

Not all functions fit the mold of what we can do with arg specs. When this
happens you may want to override the arg specs entirely. To do this,
set ``arg_specs`` to ``None``. You then have to override the ``_validate_args``
method of your plugin class, to provide your own validation and type
conversion.::

    class LenPlugin(CoreFunctionPlugin):
        """Return the length of the given item, where item can be a string,
        list, or dict."""

        def __init__(self):
            """Setup plugin"""

            super().__init__(
                name='len',
                description='Return the integer length of the given str, int or '
                            'mapping/dict.',
                arg_specs=None,
            )

        def _validate_arg(self, arg, spec):
            if not isinstance(arg, (list, str, dict)):
                raise FunctionPluginError(
                    "The list_len function only accepts lists, dicts, and "
                    "strings. Got {} of type {}.".format(arg, type(arg).__name__)
                )
            return arg

        @staticmethod
        def len(arg):
            """Just return the length of the argument."""

            return len(arg)

The Plugin Function
-------------------

As mentioned above, the plugin must define a method that takes the expected
arguments. In our example, we used a ``@static_method``, but that isn't
necessary. You may also use a regular or class method, or even assign a function
to the class directly.::

    class Min(expression_functions.FunctionPlugin):

        def __init__(self):
            super().__init__(
                name='min',
                description='Minimum value of a list',
                arg_spec=([num],)
            )

        # Just use the built-in min function. Note that the function doc string
        # will be the long form documentation for the plugin, so make sure
        # it is appropriate.
        min = min

Core Plugins
------------

Pavilion provides several built-in 'core' expression functions, but not using
the normal plugin mechanism. They're located in
``expression_functions/core.py``. If you would like to add your function to
Pavilion's core list, simply place the plugin class in that module, and make
sure it inherits from ``CoreFunctionPlugin``. A ``.yapsy-plugin`` file isn't
needed in this case.::

    class log(expression_plugins.CoreFunctionPlugin):
        def __init__(self):
            super().__init__(
                name=log,
                description="Take the log given the number and base."
                arg_specs=(num, num))

        log = math.log

