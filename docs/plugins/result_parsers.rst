.. _plugins.result_parsers:

Pavilion Result Parser Plugins
==============================

This is an overview of how to write Pavilion Result Parser plugins. It
assumes you've already read :ref:`plugins.basics`. You should also read up on
how to use :ref:`results.parse`.

.. contents::

Writing Result Parser Plugins
-----------------------------

If you're familiar with using result parsers, you'll know that they take
additional arguments like 'per_file' and 'action', and can accept multiple
files. None of those, or even the key that the result will be stored in, are
exposed to the result parser itself.

A result parser is essentially a function that takes a pre-opened file
object (automatically advanced to points of interest), plus any arguments it
specifically needs, processes that file, and returns some result data or
structure.

They also have to provide a way to validate their
arguments (to catch errors early) and define what those arguments are.

.. _yaml_config: https://yaml-config.readthedocs.io/en/latest/

Result Parser Class
-------------------

While the result parsing functionality is just a function, you still have to
define the result parser as Yapsy plugin class as detailed in
:ref:`plugins.basics`. You must give your parser a name, should give it
a description, and can give it a priority. We'll use the regex parser as an
example:

.. code-block:: python

    import yaml_config as yc
    # Remember to not import ResultParser directly to avoid yapsy confusion.
    from pavilion.result import parsers, ResultError

    class Split(parsers.ResultParser):
        """Split a line by some substring, and return the list of parts."""

        def __init__(self):
            super().__init__(
                name='split',
                description="Split by a substring, are return the whitespace "
                            "stripped parts.",
                # This adds a 'sep' configuration option to the test_config
                # format.
                config_elems=[
                    yc.StrElem(
                        'sep',
                        help_text="The substring to split by. Default is "
                                  "to split by whitespace.")],
                # Set the default value for each argument (optional)
                # (The real 'split' parser doesn't do this)
                defaults={
                    'sep': '',
                },
                # Set a validator for sep. In this case only allow these three
                # strings. (The real 'split' allows any string)
                validators={
                    'sep': (',', '', ':')
                }

            )

        def __call__(self, file, sep=None):
            """Simply use the split string method to split"""

            sep = None if sep == '' else sep

            line = file.readline().strip()

            return [part.strip() for part in line.split(sep)]

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

Every result parser gets 'action', 'per_file', and 'files', 'match_select',
'preceded_by', and 'for_lines_matching' added as arguments automatically, so
you won't have to add those. You also don't have to handle those, as they're
not passed to your result parser anyway.

Configuration items are added using the `yaml_config`_ library. Each
config item (or element in yaml_config speak) is defined using a yaml_config
instance. There are a few rules to adding such elements that apply to Pavilion.

- All values should be ``StrElem`` or a ``ListElem`` of ``StrElem`` instances.
  Pavilion expects every config value to be a string so that Pavilion
  variables and expressions can be used.
- **Don't** do any validation (or type conversions) here, even though
  ``yaml_config`` supports it.
- **Don't** set choices with ``yaml_config``.
- **Do** give the 'help_text' for each element.
- **Do** set required elements as such with 'required=True'.
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
results as errors; other exceptions are not. If your validation function
raises other exceptions, make sure to catch and convert them into ValueErrors.

File Handling (open_mode)
^^^^^^^^^^^^^^^^^^^^^^^^^

By default, your result parser function will be handed a file object that
has already been opened in text (unicode) read mode. It will also be advanced
to a position dictated by the :ref:`results.parse.line_select` options.

As a result, your result parser generally needs to only read the next line of
the file using ``file.readline()``, but it is free to read more, less, or
seek to other positions in the file as needed.

Further Validating Arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also provide a ``_check_args`` method to validate the arguments your
result parser accepts. This is in addition to the 'validators' you passed
in the init().

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

It must accept a file object as the first positional argument. The arguments
you defined in the ``__init__`` will be passed as
keyword arguments. You can accept them using either ``**kwargs`` or by just
defining them normally. If you provided a validation function, the value
passed will be the value returned from that function.


.. code-block:: python

    def __call__(self, file, sep=None):

        line = file.readline()

        return line.split(sep)


Return Value
^^^^^^^^^^^^

Your result parser should return ``None`` or an empty list if nothing was
found. Pavilion will evaluate this to ``False`` when using **store_true**.

Other than that consideration, it can return any JSON compatible structure,
though you should generally keep it simple.
