Config Elements
===============

The config specification in Yaml Config is essentially a tree of
ConfigElement instances, where ConfigElement is the base class of all
element types in the tree.

This page describes all the defined ConfigElement types. For information on
creating custom ConfigElements, see below.

Numeric Elements
-----------------
Numeric types come in a variety where choices are specified as a list, and
another where choices are given as an inclusive range.

.. autoclass:: yaml_config.IntElem
    :members: __init__

.. autoclass:: yaml_config.IntRangeElem
    :members: __init__

.. autoclass:: yaml_config.FloatElem

.. autoclass:: yaml_config.FloatRangeElem

.. autoclass:: yaml_config.BoolElem

String Elements
---------------
Both exact and regex validated versions are included.

.. autoclass:: yaml_config.StrElem

.. autoclass:: yaml_config.RegexElem
    :members: __init__

Derived Elements
----------------
This allow you to build config information from other config values.

.. autoclass:: yaml_config.DerivedElem
    :members: _resolve

Container Types
---------------
These allow you to build nested, complex configuration specifications.

.. autoclass:: yaml_config.KeyedElem
    :members: __init__

.. autoclass:: yaml_config.CategoryElem
    :members: __init__

.. autoclass:: yaml_config.ListElem
    :members: __init__

Validation
----------
Validation has several steps.
 1. The value is checked to make sure it is of the type expected, if not type
    conversion is attempted. If this fails, a ValueError is raised.
 2. If the value was None, and *required*, a RequiredError is raised.
 3. Values outside the *choices* given raise a ValueError.
 4. After all values in a container type are validated, Derived Element values
    are generated.
 5. Finally, post validation functions are run for each element in a validated
    container.

Post Validation
```````````````
Each element can also run a user provided post-validation function.
The purpose of this step is to allow for custom, user provided validation, as
well as provide a way to validate based on the values of other sibling
elements (and their children). As shown above, this step occurs last in the
validation process after all elements have their normally validated values.
The function can be provided in one of three ways, and the first found is used:

 * As the `post_validator` argument to the Element's __init__.
 * As a post_validator method on the Element itself (not defined by default).
 * As a `post_validate_<key name>` method on the container Element.

There are a couple of things to note:

 - The signature is `post_validator(siblings, value)`

   - **siblings** is all the validated data from the parent container.
   - **value** is the value of he element being validated.

 - The **return value** of the *post_validator* will replace the original value.
 - **siblings** may be a dict or list, depending on the container element.
 - Make sure siblings used in your post_validation should generally be
   *required* or have a *default*.
 - If a post-validator is found, it is expected to return the validated value.
 - In Keyed Elements and Yaml Configs, post-validators are executed in the
   order the elements were listed in *ELEMENTS*.
 - For Lists and Category Elements/Configs, the order is undefined.
 - If validation fails in a post_validator, a ValueError is expected to be
   raised. That error's message and element location will be included in a
   more specific ValueError message raised from the container.

Example: ::

    import yaml_config as yc

    class MultTenElem(yc.IntElem):
        def post_validator(self, siblings, value):
            if value % 10 != 0:
                raise ValueError("Must be a multiple of 10.")

            return value

    def bigger(siblings, value):
        if value <= siblings['by_tens']:
            raise ValueError('Must be larger than by_tens')

        return value

    class MyConfig(yc.YamlConfigLoader):
        ELEMENTS = [
            MultTenElem('by_tens', required=True),
            yc.IntElem('bigger', post_validator=bigger),
            yc.ListElem('sum_smaller', sub_elem=IntElem())
            yc.IntElem('scale', post_validator=lambda sib, val: return val*10)
        ]

        def post_validate_sum_smaller(self, siblings, list_values):
            if sum(list_values) >= siblings['by_tens']:
                raise ValueError('Total more then by_tens')

            return list_values


Creating Your Own
------------------
The ConfigElement type forms the basis for all other element types. The class
description below lists the class variables and methods expected to be
overridden, as well as those most likely to be.

.. autoclass:: yaml_config.ConfigElement
    :members: __init__, _check_range, make_comment, validate
