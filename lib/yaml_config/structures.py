from collections import defaultdict, OrderedDict
import io

import similarity

import yc_yaml as yaml
from .elements import (
    ConfigElement,
    RequiredError,
    NullList,
    ConfigDict,
)
from .scalars import ScalarElem



class ListElem(ConfigElement):
    """A list of configuration items. All items in the list must be the same
    ConfigElement type. Configuration inheritance appends new, unique items
    to these lists.

    A shortcut is allowed in the interpretation of lists, such that a single
    value is interpreted as a single valued list. Each of the following is
    valid. ::

        colors: red
        colors: [red, yellow, green]
        colors:
            - red
            - yellow
            - blue

    However, if the sub-element is another list, the lists must always be
    explicit. ::

        collections:
            - [quarter, dime, nickel]
            - [thing1, thing2, thing3]
        collections: [[quarter, dime, nickel], [thing1, thing2, thing3]

    When dumping configs, the lists are always given explicitly.

    """

    type = list
    type_name = 'list of items'

    def __init__(self, name=None, sub_elem=None, min_length=0, max_length=None,
                 defaults=None, **kwargs):
        """
        :param sub_elem: A ConfigItem that each item in the list must conform
            to.
        :param min_length: The minimum number of items allowed, inclusive.
            Default: 0
        :param max_length: The maximum number of items allowed, inclusive. None
            denotes unlimited.
        :param [] defaults: Defaults on a list are items that are added to the
            list if no items are explicitly added.
        """

        if defaults is None:
            defaults = NullList()

        if sub_elem is None:
            raise ValueError("ListElem sub_elem argument is required.")

        if min_length < 0:
            raise ValueError("min_length must be a positive integer.")
        self.min_length = min_length
        self.max_length = max_length

        super(ListElem, self).__init__(name=name, _sub_elem=sub_elem,
                                       default=defaults, **kwargs)

    def _check_range(self, value):
        """Make sure our list is within the appropriate length range."""
        vlen = len(value)
        if vlen < self.min_length:
            return False

        if self.max_length is None or vlen <= self.max_length:
            return True
        else:
            return False

    def normalize(self, value, root_name=None):
        """Lists with a value of None remain as None, and empty lists stay
        empty. Single values, however, become a list of that value. All
        contained value are recursively normalized."""

        if root_name is not None:
            name = root_name
        else: 
            name = self.name

        if value is None or value == [None]:
            return None
        elif isinstance(value, self.type):
            return [self._sub_elem.normalize(v, root_name=name) for v in value]
        else:
            return [self._sub_elem.normalize(value, root_name=name)]

    def validate(self, value, partial=False):
        """Just like the parent function, except converts None to an empty
        list, and single values of other types into the subtype for this
        list.  Subvalues are recursively validated against the subitem type
        (whose name is ignored).
        :param list value: A list of values to validate and add.
        :param bool partial: Ignore 'required'
        """

        if value is None:
            return self.default.copy()

        vvals = self.type()

        for val in value:
            vvals.append(self._sub_elem.validate(val, partial=partial))

        if not self._check_range(value):
            raise ValueError(
                "Expected [{}-{}] list items for {} field {}, got {}."
                .format(
                    self.min_length,
                    self.max_length if self.max_length is not None else 'inf',
                    self.__class__.__name__,
                    self.name,
                    len(value)))

        for i in range(len(value)):
            vvals[i] = self._run_post_validator(self._sub_elem, value,
                                                vvals[i])

        if self.required and not (partial or value):
            raise RequiredError("Required ListElem '{}' is empty."
                                .format(self.name))

        return vvals

    def _choices_doc(self):
        return "May contain {min} - {max} items.".format(
            min=self.min_length,
            max=self.max_length if self.max_length is not None else 'inf'
        )

    def find(self, dotted_key):
        if dotted_key == '':
            return self
        else:
            parts = dotted_key.split('.', maxsplit=1)
            key = parts[0]
            next_key = parts[1] if len(parts) == 2 else ''
            if key != '*':
                raise KeyError(
                    "Invalid dotted key for {} called '{}'. List elements "
                    "must have their element name given as a *, since it's "
                    "sub-element isn't named. Got '{}' from '{}' instead."
                    .format(self.__class__.__name__, self.name, key,
                            dotted_key))

            return self._sub_elem.find(next_key)

    def yaml_events(self, value, show_comments, show_choices):
        """Create the events for a ListElem."""

        events = list()
        events.append(yaml.SequenceStartEvent(
            anchor=None,
            tag=None,
            implicit=True,
            flow_style=False,
        ))

        if show_comments and (
                (not isinstance(self._sub_elem, ScalarElem) or
                 self._sub_elem.help_text)):
            comment = self._sub_elem.make_comment(
                show_choices=show_choices,
                recursive=True,
            )
            events.append(yaml.CommentEvent(value=comment))

        if not value:
            value = self.type()

        # Value is expected to be a list of items at this point.
        for val in value:
            events.extend(
                self._sub_elem.yaml_events(
                    value=val,
                    show_comments=False,
                    show_choices=show_choices))

        events.append(yaml.SequenceEndEvent())
        return events

    def merge(self, old, new, extend=False):
        """When merging lists, a new list simply replaces the old list, unless
        the new list is empty."""

        # Don't override with an empty list that was defined implicitly.
        if ((not new and isinstance(new, NullList)) or
                new is None):
            if old is None:
                return list()
            else:
                return old


        if extend and old:
            return old.copy() + new.copy()
        else:
            return new.copy()

    def comment_type_str(self):
        return '[{}]'.format(self._sub_elem.comment_type_str())


class _DictElem(ConfigElement):
    type = ConfigDict

    KC_LOWER = 'lower'
    KC_UPPER = 'upper'
    KC_MIXED = 'mixed'

    def __init__(self, key_case=None, **kwargs):

        if key_case is None:
            key_case = self.KC_MIXED

        if key_case not in (self.KC_LOWER, self.KC_UPPER, self.KC_MIXED):
            raise ValueError(
                "Invalid key case. Expected one of <cls>.KC_LOWER, "
                "<cls>.KC_UPPER, <cls>.KC_MIXED")

        self._key_case = key_case

        super(_DictElem, self).__init__(**kwargs)

    def find(self, dotted_key):
        raise NotImplementedError

    def validate(self, value, partial=False):
        raise NotImplementedError

    def _key_check(self, values_dict):
        """Raises a KeyError if keys don't match the key regex, or there are
        duplicates. Keys are converted to upper, lower, or left in their
        original case depending on 'self._key_case'.

        :param {} values_dict: The dictionary to check.
        """

        if not isinstance(values_dict, self.type):
            try:
                values_dict = self.type(values_dict)
            except (ValueError, KeyError):
                raise ValueError(
                    "Invalid values ({}) for element {}. Expected '{}'"
                    .format(values_dict, self.name, self.type))

        # Check for duplicate keys.
        keys = defaultdict(lambda: [])
        for key in values_dict.keys():
            if key is None:
                key_mod = key
            elif self._key_case is self.KC_LOWER:
                key_mod = key.lower()
            elif self._key_case is self.KC_UPPER:
                key_mod = key.upper()
            else:
                key_mod = key

            if key_mod and key_mod.endswith('+'):
                key_mod = key_mod[:-1]

            keys[key_mod].append(key)

            if key_mod is not None and self._NAME_RE.match(key_mod) is None:
                raise KeyError(
                    "Invalid key '{}' in {} called {}. Key does not match "
                    "expected regular expression '{}'"
                    .format(key_mod, self.__class__.__name__, self.name,
                            self._NAME_RE.pattern))

        for k_list in keys.values():
            if len(k_list) != 1:
                raise KeyError("Duplicate keys given {} in {} called {}. ("
                               "Keys in this config object are automatically "
                               "converted to {}case."
                               .format(k_list, self.__class__.__name__,
                                       self.name, self._key_case))

    def _merge_extend(self, key, sub_elem, old_value, value):
        """Append list items to a list element."""

        if not isinstance(sub_elem, ListElem):
            raise KeyError("Key '{}+' given under '{}', but underlying config item "
                           "isn't a list.".format(key, self.name))

        return sub_elem.merge(old_value, value, extend=True)

class KeyedElem(_DictElem):
    """A dictionary configuration item with predefined keys that may have
    non-uniform types. The valid keys are are given as ConfigItem objects,
    with their names being used as the key name."""

    type = ConfigDict
    _type_name = ''

    def __init__(self, name=None, elements=None, key_case=_DictElem.KC_MIXED,
                 **kwargs):
        """
        :param key_case: Must be one of the <cls>.KC_* values. Determines
            whether keys are automatically converted to lower or upper case,
            or left alone.
        :param elements: This list of config elements is also forms the list
            of accepted keys, with the element.name being the key.
        """

        self.config_elems = OrderedDict()

        if elements is None:
            elements = []

        super(KeyedElem, self).__init__(name=name, key_case=key_case, **kwargs)

        for i in range(len(elements)):
            self.add_element(elements[i])

    def add_element(self, elem):
        # Make sure each sub-element has a usable name that can be used
        # as a key..
        if elem.name is None:
            raise ValueError(
                "In KeyedConfig item ({}), subitem {} has name of None."
                .format(
                    self.name if self.name is not None else '<unnamed>',
                    elem))

        # Make sure derived elements have a resolver defined somewhere.
        if isinstance(elem, DerivedElem):
            self._find_resolver(elem)

        self.config_elems[elem.name] = elem

    def _find_resolver(self, elem):
        """Find the resolver function for the given DerivedElem. Try the
        elem.resolve method first, then look for a 'get_<elem.name>' method
        next. Raises a ValueError on failure."""

        if elem.resolve is not None:
            return elem.resolve
        elif hasattr(self, 'resolve_' + elem.name):
            return getattr(self, 'resolve_' + elem.name)
        else:
            raise ValueError(
                "Could not find resolver for derived element '{}' in {} "
                "called {}."
                .format(elem.name, self.__class__.__name__, self.name))

    def find(self, dotted_key):
        if dotted_key == '':
            return self
        else:
            parts = dotted_key.split('.', maxsplit=1)
            key = parts[0]
            next_key = parts[1] if len(parts) == 2 else ''
            if key not in self.config_elems:
                raise KeyError(
                    "Invalid dotted key for {} called '{}'. KeyedElem "
                    "element names must be in the defined keys. "
                    "Got '{}' from '{}', but valid keys are {}"
                    .format(self.__class__.__name__, self.name,
                            key, dotted_key, self.config_elems.keys()))

            return self.config_elems[key].find(next_key)

    find.__doc__ = ConfigElement.find.__doc__

    def find_key_matches(self, word, min_score=0.8):
        """Find similar keys to the one given."""

        return similarity.find_matches(word, self.config_elems.keys(), min_score=min_score)

    def find_sub_key_matches(self, key):
        """Find potential matches in KeyedElements under this one."""
        sub_key_matches = []
        for sub_key, config_elem in self.config_elems.items():
            if isinstance(config_elem, KeyedElem):
                similar = config_elem.find_key_matches(key, min_score=0.8)
                if similar:
                    sub_key_matches.append((sub_key, similar))

        return sub_key_matches

    def get_sub_comments(self, show_choices, show_name):
        """Add the comment description for each sub element at the top
        of Keyed Elements."""
        sub_comments = []

        for key, elem in self.config_elems.items():
            sub_comments.append('  ' + elem.make_comment(
                show_choices=True,
                show_name=show_name,
                recursive=True
            ))
        return sub_comments

    def merge(self, old, new):

        base = old.copy()

        if new is None:
            return base

        for key, value in new.items():
            if key and key.endswith('+'):
                key = key[:-1]
                base[key] = self._merge_extend(key, self.config_elems[key],
                                               old[key], value)
            elif value is not None:
                try:
                    base[key] = self.config_elems[key].merge(old[key], new[key])
                except:
                    raise


        return base

    def _make_missing_key_message(self, root_name, key, value):
        """Generate a message for when a matching key isn't found. Searches for similar
        keys in this and child KeyedElements."""

        name = root_name if root_name is not None else self.name

        msg = ["Invalid config key '{}' given under '{}'."
                   .format(key, name)]

        matches_found = False

        similar = self.find_key_matches(key)
        if similar:
            msg.append("Did you mean one of these?")
            matches_found = True
            for skey in similar:
                help_text = self.config_elems[skey].help_text
                if help_text:
                    help_text = help_text[:60] + '...'
                    msg.append('  {} - "{}"'.format(skey, help_text))
                else:
                    msg.append('  {}')

        sub_key_matches = self.find_sub_key_matches(key)
        if sub_key_matches:
            matches_found = True
            msg.append("Config elements under this one have similar keys:")
            msg.append("{}:".format(name))
            for sub_key, matches in sub_key_matches:
                msg.append("  {}:".format(sub_key))
                for match in matches:
                    help_text = self.config_elems[sub_key].config_elems[match].help_text
                    msg.append("    {}:     # {}...".format(match, help_text[:60]))

        if not matches_found:
            for sub_key, sub_elem in self.config_elems.items():
                if not isinstance(sub_elem, CategoryElem):
                    continue

                try:
                    sub_elem.normalize(value)
                except (ValueError, KeyError, AttributeError):
                    continue

                msg.append("Key '{}' not found under '{}', but the value works as a key under '{}':"
                           .format(key, root_name, sub_key))
                new_val = {root_name: {sub_key: value}}
                buffer = io.StringIO()
                yaml.dump(new_val, buffer)
                for line in buffer.getvalue().split('\n'):
                    msg.append('  ' + line)

        return '\n'.join(msg)

    def normalize(self, value, root_name=None):
        """None remains None. Everything else is recursively normalized
        by their element objects. Unknown keys and non-dict 'values'
        result in an error.
        :param dict value: The dict of values to normalize.
        :param root_name: What to call this if it is the root element.
        :raises KeyError: For unknown keys.
        :raises TypeError: if values isn't a dict.
        """

        name = root_name if root_name is not None else self.name

        if value is None:
            return None

        if not isinstance(value, dict):
            raise TypeError("Config element '{}' is expected to be "
                            "a dict/mapping, but got '{}'"
                            .format(self.name, value))

        ndict = self.type()

        for key, val in value.items():
            if key and key.endswith('+'):
                final_key = key[:-1]
            else:
                final_key = key

            elem = self.config_elems.get(final_key, None)
            if elem is None:
                msg = self._make_missing_key_message(root_name, key, value)
                raise KeyError(msg, key)

            try:
                ndict[key] = elem.normalize(val, root_name=key)
            except ValueError as err:
                if isinstance(val, dict):
                    msg = [err.args[0]]
                    msg.append("Key '{}.{}' does not take dictionary values. "
                               "Perhaps these values belong under a different key?"
                               .format(name, key))
                    raise ValueError("\n".join(msg))
                else:
                    raise
            except KeyError as err:
                # Check to see if this level takes the key that was erroneous at the next
                # level, and suggest a course of action.
                msg = err.args[0]
                if len(err.args) > 1:
                    err_key = err.args[1]

                    if err_key in self.config_elems:

                        addtl_msg = "The level above '{}' takes key '{}' - maybe key '{}' "\
                                    "is over-indented?".format(key, err_key, err_key)
                        msg = '\n'.join([msg, addtl_msg])

                raise KeyError(msg)

        return ndict

    def validate(self, value, partial=False):
        """Ensure the given values conform to the config specification. Also
            adds any derived element values.

        :param dict value: The dictionary of values to validate.
        :param bool partial: Ignore 'required'.
        :returns dict: The validated and type converted value dict.
        :raises TypeError: if type conversion can't occur.
        :raises ValueError: When the value is not within range.
        :raises RequiredError: When a required value is missing.
        :raises KeyError: For duplicate or malformed keys.
        """

        if value is None:
            if self.required and not partial:
                raise RequiredError("Missing required KeyedElem '{}' in "
                                    "config.".format(self.name))
            value = self.type()

        self._key_check(value)

        # Change the key case.
        for key in list(value.keys()):
            if self._key_case == self.KC_LOWER:
                new_key = key.lower()
            elif self._key_case == self.KC_UPPER:
                new_key = key.upper()
            else:
                new_key = key

            # Make sure extended keys are trying to extend lists.
            if new_key and new_key.endswith('+'):
                sub_elem = self.config_elems.get(key[:-1], None)
                if not isinstance(sub_elem, ListElem):
                    raise KeyError(
                        "Key '{}' given (which would extend the list of values under key '{}'), "
                        "but the values under that key aren't a list."
                        .format(key, new_key[:-1]))

                # When validating, it's ok if we end up with a '+' key. Just
                # drop the plus.
                new_key = new_key[:-1]

            if key != new_key:
                value[new_key] = value[key]
                del value[key]

        # Make sure each key is defined in the KeyedElement
        for key in value:
            if key not in self.config_elems:
                raise KeyError(
                    "Key '{}' under KeyedElem '{}' does not appear in the "
                    "elements list: {}."
                    .format(key, self.name, self.config_elems.keys())
                )

        derived_elements = []

        for key, elem in self.config_elems.items():
            if isinstance(elem, DerivedElem):
                derived_elements.append(elem)
            else:
                # Validate each of the subkeys in this dict.
                value[key] = self.config_elems[key].validate(
                    value.get(key),
                    partial=partial,
                )

        # Handle any derived elements
        for elem in derived_elements:
            value[elem.name] = self._find_resolver(elem)(value)

        # Run custom post validation against each key, if given.
        for key, elem in self.config_elems.items():
            value[key] = self._run_post_validator(elem, value,
                                                  value[key])

        return value

    def yaml_events(self, value,
                    show_comments,
                    show_choices):
        if value is None:
            value = dict()

        events = list()
        events.append(yaml.MappingStartEvent(anchor=None, tag=None,
                                             implicit=True))
        for key, elem in self.config_elems.items():
            if elem.hidden:
                continue

            # Don't output anything for Derived Elements
            if isinstance(elem, DerivedElem):
                continue

            val = value.get(key, None)
            if show_comments:
                comment = elem.make_comment(show_choices=show_choices)
                events.append(yaml.CommentEvent(value=comment))

            # Add the mapping key
            events.append(yaml.ScalarEvent(value=key, anchor=None,
                                           tag=None, implicit=(True, True)))
            # Add the mapping value
            events.extend(elem.yaml_events(val,
                                           show_comments,
                                           show_choices))
        events.append(yaml.MappingEndEvent())
        return events


class CategoryElem(_DictElem):
    """A dictionary config item where all the keys must be of the same type,
    but the key values themselves do not have to be predefined. The possible
    keys may still be restricted with the choices argument."""

    type = ConfigDict
    _type_name = ''

    def __init__(self, name=None, sub_elem=None, defaults=None, allow_empty_keys=False,
                 key_case=_DictElem.KC_MIXED, **kwargs):
        """Initialize the Config Element.
        :param name: The name of this Config Element
        :param ConfigElement sub_elem: The type all keys in this mapping must
        conform to. (required)
        :param Union(None,list) choices: The possible keys for this element.
        None denotes that any are valid.
        :param bool required: Whether this element is required.
        :param Union[dict,None] defaults: An optional dictionary of default
        key:value pairs.
        :param bool allow_empty_keys: Allow dict keys to be None when validating.
        :param str key_case: Must be one of the <cls>.KC_* values. Determines
        whether keys are automatically converted to lower or upper case,
        or left alone.
        :param help_text: Description of the purpose and usage of this element.
        """

        if defaults is None:
            defaults = dict()

        if isinstance(sub_elem, DerivedElem):
            raise ValueError(
                "Using a derived element as the sub-element in a CategoryElem "
                "does not make sense.")

        self.allow_empty_keys = allow_empty_keys

        self._sub_elem = sub_elem

        super(CategoryElem, self).__init__(name=name, _sub_elem=sub_elem,
                                           key_case=key_case,
                                           default=defaults, **kwargs)

    def normalize(self, value: dict, root_name=None):
        """Make sure values is a dict, and recursively normalize the contained
        keys. Returns None if values is None."""

        if value is None:
            return None

        out_dict = self.type()

        if not isinstance(value, dict):
            raise TypeError("Expected a dict/mapping for key '{}', got '{}'."
                            .format(self.name, value))

        for key, val in value.items():
            out_dict[key] = self._sub_elem.normalize(val, root_name=key)

        return out_dict

    def validate(self, value, partial=False):
        """Check the keys, and validate each value against the sub-elements
        validator."""

        value_dict = value

        if value_dict is None:
            if self.required and not partial:
                raise RequiredError("Missing CategoryElem '{}' in config."
                                    .format(self.name))
            value_dict = {}

        out_dict = self.type()

        # Pre-fill our output dictionary with hard coded defaults.
        if self._default is not None:
            for key, val in self._default:
                out_dict[key] = val

        # Change the key case.
        for key in list(value_dict.keys()):
            if key is None:
                if not self.allow_empty_keys:
                    raise ValueError("Invalid key for {} - key value is None.".format(self.name))
                new_key = key
            elif self._key_case == self.KC_LOWER:
                new_key = key.lower()
            elif self._key_case == self.KC_UPPER:
                new_key = key.upper()
            else:
                new_key = key

            if new_key and new_key.endswith('+'):
                if not isinstance(self._sub_elem, ListElem):
                    raise KeyError(
                        "Key '{}' tried to extend non-list key '{}'."
                        .format(key, new_key[:-1]))
                new_key = new_key[:-1]

            if key != new_key:
                value_dict[new_key] = value_dict[key]
                del value_dict[key]

        for key, val in value_dict.items():
            if self._choices is not None and key not in self._choices:
                raise ValueError(
                    "Invalid key for {} called {}. '{}' not in given choices."
                    .format(self.__class__, self.name, key)
                )

            validated_value = self._sub_elem.validate(val, partial=partial)
            # Merge the validated values with the defaults from the hard
            # coded defaults if present.
            if key in out_dict:
                out_dict[key] = self._sub_elem.merge(out_dict[key],
                                                     validated_value)
            else:
                out_dict[key] = validated_value

        # Make sure the keys are sane
        self._key_check(value_dict)

        for key, val in out_dict.items():
            out_dict[key] = self._run_post_validator(self._sub_elem, out_dict,
                                                     val)

        return out_dict

    def merge(self, old, new):
        base = old.copy()

        if new is None:
            return base

        for key, value in new.items():
            if key and key.endswith('+'):
                key = key[:-1]
                old_value = old.get(key, [])
                base[key] = self._merge_extend(key, self._sub_elem, old_value, value)
            else:
                old_value = old.get(key)
                if old_value is None:
                    base[key] = value
                else:
                    base[key] = self._sub_elem.merge(old_value, value)

        return base

    def find(self, dotted_key):
        if dotted_key == '':
            return self
        else:
            parts = dotted_key.split('.', maxsplit=1)
            key = parts[0]
            next_key = parts[1] if len(parts) == 2 else ''
            if key != '*':
                raise KeyError(
                    "Invalid dotted key for {} called '{}'. CategoryElem"
                    "must have their element name given as a *, since it's "
                    "sub-element isn't named. Got '{}' from '{}' instead."
                    .format(self.__class__.__name__, self.name,
                            key, dotted_key))

            return self._sub_elem.find(next_key)

    def yaml_events(self, value, show_comments, show_choices):
        """Create a mapping event list, based on the values given."""
        if value is None:
            value = dict()

        events = list()
        events.append(yaml.MappingStartEvent(anchor=None, tag=None,
                                             implicit=True))
        if show_comments:
            comment = self._sub_elem.make_comment(
                show_choices=show_choices,
                show_name=False)
            events.append(yaml.CommentEvent(value=comment))
        if value:
            for key, val in value.items():
                # Add the mapping key.
                events.append(yaml.ScalarEvent(value=key, anchor=None,
                                               tag=None,
                                               implicit=(True, True)))
                # Add the mapping value.
                events.extend(
                    self._sub_elem.yaml_events(
                        val,
                        show_comments,
                        show_choices))

        events.append(yaml.MappingEndEvent())
        return events


# ext_print: 30
class DefaultedCategoryElem(CategoryElem):
    """This allows you to create a category with user defined defaults. It's
    essentially a category element with a KeyedElem as the sub-element. If
    the '__default__' key is present, values from that dict act as defaults
    for the others. The elements of the '__default__' key are all considered
    optional, regardless of whether they are marked as required or not.

    Example: ::

        import yaml_config as yc

        cars = yc.DefaultedElement(elements=[
            yc.IntElem('wheels', required=True),
            yc.StrElem('drivetrain', required=True, default='2WD'),
            yc.StrElem('color')
        ]

        results = cars.validate({
            '__default__': {
                'wheels': 4,
                'color': 'red'},
            'jeep': {
                'color': 'blue',
                'drivetrain': '4WD'},
            'reliant_robin': {
                'wheels': 3}
            })

        # Should be 4
        results.jeep.wheels
    """

    def __init__(self, name=None, elements=None, default_key='_', **kwargs):
        """
        :param elements: A list of ConfigElement instances, just like for a
        KeyedElem.
        :param default_key: The key to use for default values.
        """
        self.default_key = default_key

        super(DefaultedCategoryElem, self).__init__(name=name,
                                                    sub_elem=KeyedElem(
                                                        elements),
                                                    **kwargs)

    def validate(self, value, partial=False):
        value_dict = value

        out_dict = self.type()

        # Make sure the keys are sane
        self._key_check(value_dict)

        defaults = {}
        if self.default_key in value_dict:
            defaults = value_dict[self.default_key]
            del value_dict[self.default_key]

        # Prefill our output dictionary with hard coded defaults.
        if self._default is not None:
            for key, val in self._default:
                out_dict[key] = val

        for key, base_value in value_dict.items():
            key = key.lower()
            if self._choices is not None and key not in self._choices:
                raise ValueError(
                    "Invalid key for {} called {}. '{}' not in given choices.")

            # Use the defaults from self.DEFAULT_KEY as the base for each value.
            val = defaults.copy()
            # We know our sub-element is a dict in this case.
            val.update(base_value)
            validated_value = self._sub_elem.validate(val, partial)
            # Merge the validated values with the defaults from the hard
            # coded defaults if present.
            if key in out_dict:
                out_dict[key] = self._sub_elem.merge(out_dict[key],
                                                     validated_value)
            else:
                out_dict[key] = validated_value

        for key, val in out_dict.items():
            out_dict[key] = self._run_post_validator(self._sub_elem, out_dict,
                                                     val)

        return out_dict


class DerivedElem(ConfigElement):
    """The value is derived from the values of other elements. This is only
    valid when used as an element in a KeyedElem (or YamlConfigLoader),
    trying to use it elsewhere will raise an exception (It simply doesn't
    make sense anywhere else).

    Resolution of this element is deferred until after all non-derived
    elements are resolved. All derived elements are then resolved in the
    order they were listed. This resolution is performed by a function,
    which can be given either:

      - As the 'resolver' argument to __init__
      - The 'resolve' method of this class
      - The 'resolve_<name>' method of the parent KeyedElem or
        YamlConfigLoader class.

    This function is expected to take one positional argument, which is the
    dictionary of validated values from the KeyedElem so far.
    """

    def __init__(self, name, resolver=None, **kwargs):
        if name is None:
            raise ValueError("Derived Elements must be named.")

        if resolver is not None:
            self.resolve = resolver
        else:
            self.resolve = self._resolve

        super(DerivedElem, self).__init__(name=name, _sub_elem=None, **kwargs)

    def _resolve(self, siblings):
        """A resolver function gets a dictionary of its returned sibling's
        values, and should return the derived value. A resolver passed as an
        argument to DerivedElem's __init__ should have the same signature (
        without the self).

        :param {} siblings: The dictionary of validated values from the
            keyed element that this is a part of.
        :returns: The derived element value
        """

        # Using vars to get rid of syntax notifications.
        _ = self, siblings

        return None

    def find(self, dotted_key):
        if dotted_key != '':
            raise ValueError(
                "Invalid key '{0}' for {1} called '{2}'. Since {1} don't have"
                "sub-elements, the key must be '' by this point."
                .format(dotted_key, self.__class__.__name__, self.name))
        return self

    # pylint: disable=no-self-use
    def yaml_events(self, value, show_comments, show_choices):
        """Derived elements are never written to file."""

        return []

    def set_default(self, dotted_key, value):
        raise RuntimeError("You can't set defaults on derived elements.")
