.. _plugins.result_parsers:

Pavilion Result Parser Plugins
==============================

This is an overview of how to write Pavilion Result Parser plugins. It
assumes you've already read :ref:`plugins.basics`. You should also read up on
how to use :ref:`tests.results.result_parsers`.

.. contents::

Writing Result Parser Plugins
-----------------------------

If you're familiar with using result parsers, you'll know that they take
additional arguments like 'per_file' and 'action', and can accept multiple
files. None of those, or even the key that the result will be stored in, are
exposed to the result parser itself.

A result parser is essentially a function that takes a pre-opened file
object, plus any arguments it specifically needs, processes that file, and
returns some result data or structure.

They also have to provide a way to validate their
arguments (to catch errors early) and define what those arguments are.

.. _yaml_config: https://yaml-config.readthedocs.io/en/latest/

Result Parser Class
-------------------

While the result parsing functionality is just a function, you still have to
define the result parser as Yapsy plugin class as detailed in
:ref:`plugins.basics`. You must give your parser a name, should give it
a description, and can give it a priority.

.. code-block:: python

    import yaml_config as yc

    class Command(parsers.ResultParser):
        """Runs a given command."""

        def __init__(self):
            super().__init__(
                name='command',
                description="Runs a command, and uses it's output or return "
                            "values as a result value.",
                config_elems=[
                    yc.StrElem(
                        'command', required=True,
                        help_text="Run this command in a sub-shell and collect "
                                  "its return value or stdout."
                    ),
                    yc.StrElem(
                        'output_type',
                        help_text="Whether to return the return value or stdout."
                    ),
                    yc.StrElem(
                        'stderr_dest',
                        help_text="Where to redirect stderr."
                    )
                ],
                validators={
                    'output_type': ('return_value', 'stdout'),
                    'stderr_dest': ('null', 'stdout'),
                },
                defaults={
                    'output_type': 'return_value',
                    'stderr_dest': 'stdout',
                }
            )

Additional Arguments
~~~~~~~~~~~~~~~~~~~~

Result parsers use a few additional properties to tell Pavilion how to work
with it.

Arguments (config_elems)
^^^^^^^^^^^^^^^^^^^^^^^^

The arguments to your parser are actually configuration items within the
Pavilion test config format. By adding a result parser, you add a new section
that can appear under ``result_parse`` in your test configs. Dynamically
adding to a config like this can be complicated, but Pavilion takes care of
all of the difficult bits for you.

Every result parser gets 'action', 'per_file', and 'files' added as arguments
automatically, so you won't have to add those.

Configuration items are added using the `yaml_config`_ library. Each
config item (or element in yaml_config speak) is defined using a yaml_config
instance. There are a few rules to adding such elements that apply to Pavilion.

- All values should be ``StrElem`` or a ``ListElem`` of ``StrElem`` instances.
  Pavilion expects every config value to be a string so that Pavilion
  variables can be used.
- **Don't** do any validation (or type conversions) here, even though
  ``yaml_config`` supports it.
- **Don't** set choices with ``yaml_config``.
- Do give the 'help_text' for each element.
- Do set required elements as such with 'required=True'.
- The order of your arguments doesn't matter.

Multi-Valued Config Elements
''''''''''''''''''''''''''''

To add an config item that can take one or more values, use ``ListElem``:

.. code-block:: python

    def __init__(self):
        super().__init__(
            name="example",
            description="Look for the given tokens, and set this as true if "
                        "any are found."
            config_elems=[
                yc.ListElem(
                    'tokens', sub_elem=StrElem(),
                    help_text="One or more tokens to look for."
                )
            ]
        )

The 'match_type' Argument
'''''''''''''''''''''''''

If your parser may return multiple items, consider using the pre-defined
standard 'match_type' configuration element. It provides a standard way for
the user to tell your plugin whether they want all of those items, or just
the first or last. Plugins that use this will need to accept a 'match_type'
argument that should change what your result parser returns:

- **all** - Return a list of all matched values.
- **first** - Return only the first matched value.
- **last** - Return only the last matched value.

The 'match_type' argument is automatically validated and will have its default
set for you.


Argument Defaults (defaults)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The 'defaults' ``__init__()`` argument takes a dictionary of default values
for each of the result parser arguments. Always give these as strings
compatible with your argument validation.

Argument Validators (validators)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The 'validators' ``__init__()`` argument takes a dictionary of validators
for each of the result parser arguments. It can either be a tuple of valid
choices (all strings) or a function that takes a single argument and returns
the validated value.

Type conversion functions, like ``int`` or ``float``, are all valid here.

ValueError exceptions are caught during validation and reported in the
results as errors;
other exceptions are not. If your validation function raises other
exceptions, make sure to catch and convert them into ValueErrors.


File Handling (open_mode)
^^^^^^^^^^^^^^^^^^^^^^^^^

By default, your result parser function will be handed a file object that
has already been opened in text (unicode) read mode. The ``open_mode`` class
property can be used to change what mode the file should be opened in. Any
string is handed directly to Python's ``open`` function.

The value ``None``, however, tells Pavilion that your function would like the
path instead (given as a pathlib.Path object).


Further Validating Arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also provide a ``_check_args`` method to validate the arguments your
result parser accepts.

  - Catch any expected exceptions (let bug related exceptions through).
    - On type conversions, catch `ValueError`.
    - Catch OSError on system calls or file manipulation.
    - Catch library specific errors as needed.
  - After catching those exceptions, raise a Pavilion ``ResultError``
    that contains a helpful message and the erroneous value and/or the
    original error message.

    - Formatting works best when the error messages are included directly
      from the exception object, rather than simply formatting the exception
      itself. Mostly, this means inserting ``err.args[0]``.
    - Pavilion will extend that information so that the user can easily find
      where in their config the error occurred.
  - The ``_check_args`` method should take the expected arguments as keyword
    arguments.
  - The ``_check_args`` method should return a dictionary of the arguments
    with any defaults or formatting changes applied. These will be passed
    directly to your result_parser function.


.. code-block:: python

    # The _check_args method for the regex parser.
    def _check_args(self, **kwargs):

        try:
            re.compile(kwargs.get('regex'))
        except (ValueError, sre_constants.error) as err:
            raise pavilion.result.base.ResultError(
                "Invalid regular expression: {}".format(err.args[0]))

        return kwargs


Result Parsing Function
~~~~~~~~~~~~~~~~~~~~~~~

Result parsers use the special ``__call__()`` method to define the result
parser function (This lets python use the class as a function, but that
doesn't matter here).

It must accept a test object and the file object as the first two positional
arguments. The arguments you defined in the ``__init__`` will be passed as
keyword arguments. You can accept them using either ``**kwargs`` or by just
defining them normally. Any values you set as defaults should always be
ignored, so you can just set them to None.


.. code-block:: python

    def __call__(self, test, file, regex=None, match_type=None):

        matches = []

        for line in file.readlines():
            # Find all non-overlapping matches and return them as a list.
            # if more than one capture is used, list contains tuples of
            # captured strings.
            matches.extend(regex.findall(line))

        if match_type == parsers.MATCH_ALL:
            return matches
        elif match_type == parsers.MATCH_FIRST:
            return matches[0] if matches else None
        elif match_type == parsers.MATCH_LAST:
            return matches[-1] if matches else None


Return Value
^^^^^^^^^^^^

Your result parser should return ``None`` or an empty list if nothing was
found. Pavilion will evaluate this to ``False`` when using **store_true**.

Other than that consideration, it can return any JSON compatible structure,
though you should generally keep it simple.
