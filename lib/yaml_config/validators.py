# This sub-module is meant for the creation of common post_validator functions


def is_sib_key(sib_name):
    """Create a post-validator function that makes sure the value of this
    item is a key in the sibling dictionary 'sib_name'. Raises a ValueError
    if not.

    This generally assumes siblings[sib_name] is a required CategoryElement.

    :param sib_name: The name of the sibling to check the keys of.
    :return: The described post-validation function.
    """

    def is_sib_key_val(siblings, value):
        if value not in siblings[sib_name].keys():
            raise ValueError(
                "Must be a key of {}, but got {}"
                .format(sib_name, value))

        return value

    return is_sib_key_val
