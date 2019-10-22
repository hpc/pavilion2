# This module contains functions and classes for building variable sets for
# string insertion.
# There are three layers to every variable:
#   - A list of variable values
#   - A dictionary of sub-keys
#   - The values of those sub keys.
#   ie: [{key:value},...]
#
# From the user perspective, however, all but the value itself is optional.
#
# While variables are stored in this manner, these layers are automatically
# resolved in the trivial cases such as when there is only one element, or a
# single value instead of a set of key/value pairs.
#
# There are expected to be multiple variable sets; plain variables (var),
# permutations (per), plugin provided via 'sys', core pavilion provided (pav),
# and scheduler provided (sched).
#
# Additionally, variables can have a deferred value. These objects result
# in an escape sequence being inserted that is resolved before the test is
# run in its final environment.

import re
import copy


class VariableError(ValueError):
    """This error should be thrown when processing variable data,
    and something goes wrong."""

    def __init__(self, message, var_set=None, var=None, index=None,
                 sub_var=None):

        super().__init__(message)

        self.var_set = var_set
        self.var = var
        self.index = index
        self.sub_var = sub_var

        self.base_message = message

    def __str__(self):

        key = [self.var]
        if self.var_set is not None:
            key.insert(0, self.var_set)
        if self.index is not None and self.index != 0:
            key.append(self.index)
        if self.sub_var is not None:
            key.append(self.sub_var)

        key = '.'.join(key)

        return "Error processing variable key '{}': {}" \
            .format(key, self.base_message)


class DeferredVariable:
    """The value for some variables may not be available until a test is
    actually running."""

    # NOTE: Other than __init__, this should always have the same interface
    # as VariableList.

    VAR_TEMPLATE = '[\x1e{key}\x1e]'
    ALLOWED_VARSETS = ['sys', 'pav', 'sched']

    def __init__(self, name, var_set='sys', sub_keys=None):
        """Deferred variables need to know their name and var_set at definition
        time. Additionally, they need to be aware of their valid sub-keys.
        They cannot have more than one value, like normal variables.
        :param name: The name of this variable.
        :param var_set: The variable set this deferred variable belongs to.
            Only some varsets are allowed, as defined in
            DeferredVariable.ALLOWED_VARSETS.
        :param list sub_keys: A list of subkey names for the variable. None
            denotes sub-keys aren't used.
        """

        if var_set not in self.ALLOWED_VARSETS:
            raise ValueError("The allowed values of var_set are {}. Got {}."
                             .format(self.ALLOWED_VARSETS, var_set))

        self.name = name
        self.var_set = var_set

        if sub_keys is None:
            sub_keys = list()

        self.sub_keys = sub_keys

    def get(self, index, sub_var):
        if index not in [0, None]:
            raise KeyError("Deferred variables only have a single value.")

        key = [self.var_set, self.name]

        if sub_var is None and self.sub_keys:
            raise KeyError('Sub variable not requested, but must be one of {}'
                           .format(self.sub_keys))
        elif sub_var is not None and not self.sub_keys:
            raise KeyError(
                'Sub variable {} requested for a deferred variable with no '
                'sub-keys.'.format(sub_var))
        elif sub_var is not None and sub_var not in self.sub_keys:
            raise KeyError(
                'Sub variable requested ({}) that is not in the known sub-key '
                'list ({})'.format(sub_var, self.sub_keys))

        if sub_var is not None:
            key.append(sub_var)

        return self.VAR_TEMPLATE.format(key='.'.join(key))

    def __len__(self):
        """Deferred variables always have a single value."""
        return 1

    def __repr__(self):
        return ('DeferredVariable({s.name}, {s.var_set}, {s.sub_keys})'
                .format(s=self))


class VariableSetManager:
    """This class manages the various sets of variables, provides complex key
    based lookups, manages conflict resolution, and so on."""

    # The variable sets, in order of resolution.
    VAR_SETS = ('per', 'var', 'sys', 'pav', 'sched')

    def __init__(self):
        """Initialize the var set manager."""

        self.variable_sets = {}

        self.reserved_keys = []
        self.reserved_keys.extend(self.VAR_SETS)

    def add_var_set(self, name, value_dict):
        """Add a new variable set to this variable set manager. Variables in
        the set can then be retrieved by complex key.
        :param str name: The name of the var set. Must be one of the reserved
            keys.
        :param dict value_dict: A dictionary of values to populate the var set.
        :return: None
        :raises VariableError: On problems with the name or data.
        """
        if name not in self.reserved_keys:
            raise ValueError("Unknown variable set name: '{}'".format(name))

        if name in self.variable_sets:
            raise ValueError(
                "Variable set '{}' already initialized.".format(name))

        try:
            var_set = VariableSet(name, self.reserved_keys,
                                  value_dict=value_dict)
        except VariableError as err:
            # Update the error to include the var set.
            err.var_set = name
            raise err

        self.variable_sets[name] = var_set

    def get_permutations(self, used_per_vars):
        """For every combination of permutation variables (that were used),
        return a new var_set manager.
        :param set used_per_vars: A list of permutation variable names that
            were used.
        :return:
        """

        # Get every a dictionary of var:idx for every combination of used
        # permutation variables.
        permutations = [{}]
        for var_set, var in used_per_vars:
            new_perms = []

            for old_perm in permutations:
                for i in range(self.len(var_set, var)):
                    new_perm = old_perm.copy()
                    new_perm[(var_set, var)] = i
                    new_perms.append(new_perm)

            permutations = new_perms

        permuted_var_mans = []

        if len(permutations) == 1:
            return [self]

        # Create a new var set manager for each permutation.
        for perm in permutations:
            var_man = VariableSetManager()

            var_man.variable_sets = copy.deepcopy(self.variable_sets)

            for (var_set, var), idx in perm.items():
                new_list = [self.variable_sets[var_set][var][idx]]
                vlist = VariableList()
                vlist.data = copy.deepcopy(new_list)

                var_man.variable_sets[var_set].data[var] = vlist

            permuted_var_mans.append(var_man)

        return permuted_var_mans

    @classmethod
    def parse_key(cls, key):
        """Parse the given complex key, and return a reasonable (var_set, var,
            index, sub_var) tuple.
        :param Union(str,list,tuple) key: A 1-4 part key. These may either be
            given as a list/tuple of strings, or dot separated in a string. The
            components are var_set, var, index, and sub_var. Var is required,
            the rest are optional. Index is expected to be an integer, and
            var_set is expected to be a key category.
        :raises KeyError: For bad keys.
        :raises TypeError: When the key isn't a string.
        :returns: A (var_set, var, index, sub_var) tuple. Any component except
            var may be None.
        """

        if isinstance(key, list) or isinstance(key, tuple):
            parts = list(key)
        elif isinstance(key, str):
            parts = key.split('.')
        else:
            raise TypeError(
                "Only str keys or tuples/lists are allowed. Got '{}'"
                .format(key))

        var_set = None
        if parts[0] in cls.VAR_SETS:
            var_set = parts[0]

            parts = parts[1:]

        if parts:
            var = parts.pop(0)
            if var == '':
                raise KeyError("Empty variable name for key '{}'".format(key))

        else:
            raise KeyError("No variable name given for key '{}'".format(key))

        # Grab the index and sub_var parts, if present.
        index = None
        if parts:
            if parts[0] is None:
                # We were given an explicit None in a variable tuple.
                parts.pop(0)
            elif parts[0] == '':
                # Note: The index is optional. This is for when it's given as
                # an empty string.
                raise KeyError("Invalid, empty index in key: '{}'".format(key))
            else:
                try:
                    index = int(parts[0])
                except ValueError:
                    # If it's not an integer, assume it's a sub_key.
                    pass
                else:
                    parts.pop(0)

        sub_var = None
        if parts:
            sub_var = parts.pop(0)

            if sub_var == '':
                raise KeyError(
                    "Invalid, empty sub_var in key: '{}'".format(key))

        if parts:
            raise KeyError(
                "Variable reference ({}) has too many parts, or an invalid "
                "variable set (should be one of {})".format(key, cls.VAR_SETS))

        return var_set, var, index, sub_var

    def resolve_key(self, key):
        """Resolve the given key using this known var sets. Unlike parse_key,
            the var_set returned will never be None, as the key must
            correspond to a found variable in a var_set. In case of
            conflicts, the var_set will be resolved in order.
        :param Union(str,list,tuple) key: A 1-4 part key. These may either be
            given as a list/tuple of strings, or dot separated in a string.
            The components are var_set, var, index, and sub_var. Var is
            required, the rest are optional. Index is expected to be an
            integer, and var_set is expected to be a key category.
        :raises KeyError: For bad keys, and when the var_set can't be found.
        :returns: A tuple of (var_set, var, index, sub_var), index and sub_var
            may be None.
        """

        var_set, var, index, sub_var = self.parse_key(key)

        # If we didn't get an explicit var_set, find the first matching one
        # with the given var.
        if var_set is None:
            for res_vs in self.reserved_keys:
                if (res_vs in self.variable_sets and
                        var in self.variable_sets[res_vs]):
                    var_set = res_vs
                    break

        if var_set is None:
            raise KeyError(
                "Could not find a variable named '{}' in any variable set."
                .format(var))

        return var_set, var, index, sub_var

    @staticmethod
    def key_as_dotted(key):
        """Turn a tuple based key reference back into a dotted string."""

        if isinstance(key, str):
            return key
        else:
            return '.'.join([str(k) for k in key if k is not None])

    def __getitem__(self, key):
        """Find the item that corresponds to the given complex key.
        :param Union(str, list, tuple) key: A variable key. See parse_key for
            more.
        :return: The value for the given key.
        :raises KeyError: If the key value can't be found.
        """

        var_set, var, index, sub_var = self.resolve_key(key)

        # If anything else goes wrong, this will throw a KeyError
        try:
            return self.variable_sets[var_set].get(var, index, sub_var)
        except KeyError as msg:
            # Make sure our error message gives the full key.
            raise KeyError(
                "Could not resolve reference '{}': {}"
                .format(self.key_as_dotted(key), msg))

    def is_deferred(self, var_set, var):
        """Return whether the given variable in the given varset is a
        deferred variable."""

        return isinstance(self.variable_sets[var_set].data[var],
                          DeferredVariable)

    def len(self, var_set, var):
        """
        Get the length of the given key.
        :param str var_set: The var set to fetch from.
        :param str var: The variable to fetch.
        :return: The number of items in the found 'var_set.var', the index and
            sub_var are ignored.
        :raises KeyError: When the key has problems, or can't be found.
        """

        if var_set not in self.variable_sets:
            raise KeyError("Unknown variable set '{}'".format(var_set))

        _var_set = self.variable_sets[var_set]

        if var not in self.variable_sets[var_set].data:
            raise KeyError(
                "Variable set '{}' does not contain a variable named '{}'. "
                "Available variables are: {}"
                .format(var_set, var,
                        tuple(self.variable_sets[var_set].data.keys())))

        return len(_var_set.data[var])

    @classmethod
    def has_deferred(cls, struct):
        """Return True if the config structure contains any deferred
        variables."""

        if isinstance(struct, str):
            if '[\x1b' in struct and '\x1b]' in struct:
                return True
            else:
                return False
        elif isinstance(struct, list):
            return any([cls.has_deferred(val) for val in struct])
        elif isinstance(struct, dict):
            return any([cls.has_deferred(val) for val in struct.values()])
        else:
            raise RuntimeError("Config structure contains invalid data types:"
                               "{}".format(struct))

    def resolve_deferred(self, struct):
        """Traverse the given config structure and resolve any deferred
        variables found.
        :param Union(list, dict, str) struct: The config structure to resolve.
        :rtype: Union(list, dict, str)
        """

        if isinstance(struct, str):
            return self.resolve_deferred_str(struct)
        elif isinstance(struct, list):
            for i in range(len(struct)):
                struct[i] = self.resolve_deferred(struct)
            return struct
        elif isinstance(struct, dict):
            for key in struct.keys():
                struct[key] = self.resolve_deferred(struct[key])
            return struct
        else:
            raise RuntimeError("Config structure contains invalid data types:"
                               "{}".format(struct))

    # Deferred variables will be enclosed in ascii record separators enclosed
    # in square brackets. We look for this, even with keys that can't be
    # correct, to more easily find errors in how we write these files.
    DEFERRED_VAR_RE = re.compile(r'\[\x1E((?:\x1E[^\]]|[^\x1E])*)\x1E\]')

    def resolve_deferred_str(self, line):
        """Resolve any deferred variables in the given string, and return
        the result.
        :param str line: The text to resolve.
        :rtype: str
        """

        resolved_line = []
        offset = 0

        match = self.DEFERRED_VAR_RE.search(line, offset)

        # Walk through the line, and lookup the real value of
        # each matched deferred variable.
        while match is not None:
            resolved_line.append(line[offset:match.start()])
            offset = match.end()
            var_name = match.groups()[0]
            # This may raise a KeyError, which callers should
            # expect.
            resolved_line.append(self[var_name])
            match = self.DEFERRED_VAR_RE.search(line, offset)

        # Don't forget the remainder of the line.
        resolved_line.append(line[offset:])

        resolved_line = ''.join(resolved_line)

        # Make sure all of our escape sequences are accounted for.
        if '\x1e]' in resolved_line or '[\x1e' in resolved_line:
            raise ValueError("Errant escape sequence '{}'"
                             .format(resolved_line))

        return resolved_line

    def resolve_references(self, parser):
        """
        Resolves variable references
        :param parser: String parser to parse variable value into a PavString
        :return:
        """

        unresolved_vars = {}
        # We only want to resolve variable references in the variable section
        # Find all the variable value strings that reference variables
        for var, var_list in self.variable_sets['var'].data.items():
            # val is a list of dictionaries
            for idx in range(len(var_list.data)):
                sub_var = var_list.data[idx]
                # We equate idx 0 with None. It just needs consistency.
                idx = None if idx == 0 else idx
                for key, val in sub_var.data.items():
                    pav_str = parser(val)
                    if pav_str.variables:
                        # Unresolved variable reference that will be
                        # resolved below
                        unresolved_vars[('var', var, idx, key)] = pav_str
                    else:
                        # This one is ready to resolve now
                        sub_var.data[key] = pav_str.resolve(self)

        # unresolved variables form a tree where the leaves should all be
        # resolved variables. This iteratively finds unresolved variables whose
        # references are resolved and resolves them. This should collapse the
        # tree until there are no unresolved variables left.
        while unresolved_vars:
            did_resolve = False
            for uvar, pav_str in unresolved_vars.copy().items():
                for var_str in pav_str.variables:
                    var_key = self.resolve_key(var_str)
                    if var_key in unresolved_vars:
                        break
                else:
                    # All variables referenced in uvar are resolvable
                    var_set, var_name, index, sub_var = uvar
                    self.variable_sets[var_set][var_name][index][sub_var] = \
                        pav_str.resolve(self)
                    del unresolved_vars[uvar]
                    did_resolve = True
            # If no variable is resolved in this iteration, then all remaining
            # unresolved variables are part of a variable reference loop and
            # therefore cannot eventually be resolved.
            if not did_resolve:
                var_set, var, idx, sub_var = list(unresolved_vars.keys())[0]
                raise VariableError(
                    "Variable contained reference loop"
                    .format([k[1] for k in unresolved_vars.keys()]),
                    var_set=var_set,
                    var=var,
                    index=idx,
                    sub_var=sub_var
                )

    def as_dict(self):
        """Return the all variable sets as a single dictionary. This is
        for testing and bug resolution, not production code."""

        dvar_sets = {}

        for var_set in self.variable_sets.values():
            dvar_sets[var_set.name] = {}

            for var_name in var_set.data.keys():
                dvar_sets[var_set.name][var_name] = []
                item = var_set.data[var_name]

                if isinstance(item, DeferredVariable):
                    dvar_sets[var_name] = repr(item)
                else:
                    for subitem in var_set.data[var_name].data:
                        dvar_sets[var_set.name][var_name].append(subitem.data)
        return dvar_sets

    def __contains__(self, item):

        var_set, var, index, sub_var = self.parse_key(item)

        # If we didn't get an explicit var_set, find the first matching one
        # with the given var.
        if var_set is None:
            for res_vs in self.reserved_keys:
                if (res_vs in self.variable_sets and
                        var in self.variable_sets[res_vs]):
                    var_set = res_vs
                    break

        if var_set is None:
            return False
        else:
            return True


class VariableSet:
    """A set of of variables. Essentially a wrapper around a mapping of var
        names to VariableList objects."""

    def __init__(self, name, reserved_keys=None, value_dict=None):
        """Initialize the VariableSet. The data can be set directly by
            assigning to .data, or from a config with the 'init_from_config'
            method.
        :param name: The name of this var set.
        :param reserved_keys: The list of reserved keys. Needed to check the
            given var names.
        :param value_dict: A mapping of var names to strings (str), a list of
            strings, a dict of strings, or a list of dict of strings.
        """

        self.data = {}
        self.name = name

        if value_dict is not None:
            self._init_from_config(reserved_keys, value_dict)

    def _init_from_config(self, reserved_keys, value_dict):
        """Initialize the variable set from a config dictionary.
        :param value_dict: A mapping of var names to strings (str), a list of
            strings, a dict of strings, or a list of dict of strings.
        """

        for key, value in value_dict.items():
            if key in reserved_keys:
                raise VariableError("Var name '{}' is reserved.".format(key),
                                    var=key)

            if isinstance(value, DeferredVariable):
                self.data[key] = value
            else:
                try:
                    self.data[key] = VariableList(values=value)
                except VariableError as err:
                    err.var = key
                    raise err

    def get(self, var, index, sub_var):
        """Return the value of the var given the var name, index, and sub_var
            name."""

        return self[var].get(index, sub_var)

    def __contains__(self, item):
        return item in self.data

    def __deepcopy__(self, memodict=None):
        variable_set = VariableSet(
            name=self.name
        )
        variable_set.data = copy.deepcopy(self.data)
        return variable_set

    def __getitem__(self, key):

        if key not in self.data:
            raise KeyError(
                "Variable set '{}' does not contain a variable named '{}'. "
                "Available variables are: {}"
                .format(self.name, key, tuple(self.data.keys())))
        return self.data[key]

    def __repr__(self):
        return '<VarSet({}) {}>'.format(id(self.data), self.data)


class VariableList:
    """Wraps a list of SubVariable objects. Even variables with a single value
        end up as a list (of one)."""

    def __init__(self, values=None):
        """Initialize the Varialbe list.
        :param values: A list of strings (str) or dicts of strings. The dicts
            must have the same keys.
        """

        self.data = []

        if values is not None:
            self._init_from_config(values)

    def _init_from_config(self, values):
        """Initialize the variable list from the given config values.
        :param values: A list of strings (str) or dicts of strings. The dicts
            must have the same keys.
        """

        sub_vars = None

        if not isinstance(values, list):
            values = [values]

        for idx in range(len(values)):
            value_pairs = values[idx]
            if not isinstance(value_pairs, dict):
                value_pairs = {None: value_pairs}

            if sub_vars is None:
                sub_vars = set(value_pairs.keys())
            elif set(value_pairs.keys()) != sub_vars:
                raise VariableError(
                    "Sub-keys do no match across variable values.",
                    index=str(idx))

            try:
                self.data.append(SubVariable(value_pairs))
            except VariableError as err:
                err.index = str(idx)
                raise err

    def get(self, index, sub_var):
        """Return the variable value at the given index and sub_var."""

        return self[index].get(sub_var)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return "<VariableList({}) {}>".format(id(self.data), self.data)

    def __deepcopy__(self, memodict=None):
        var_list = VariableList()
        var_list.data = copy.deepcopy(self.data)
        return var_list

    def __getitem__(self, index):

        if index is None:
            index = 0
        else:
            if not isinstance(index, int):
                raise KeyError("Non-integer index given: '{}'".format(index))

        if not -len(self.data) <= index < len(self.data):
            raise KeyError(
                "Index out of range. There are only {} items in this variable."
                .format(len(self.data)))

        return self.data[index]


class SubVariable:
    """The final variable tier. Variables with no sub-var end up with a dict
        with a single None: value pair."""

    def __init__(self, value_pairs=None):
        """Initialize the sub_variable.
        :param dict value_pairs: The value of the sub_variable, via a
            configuration.
        """

        self.data = {}

        if value_pairs is not None:
            self._init_from_config(value_pairs)

    def _init_from_config(self, value_pairs):
        for key, value in value_pairs.items():
            if not isinstance(value, str):
                raise VariableError(
                    "Variable values must be unicode strings, got '{}'"
                    .format(type(value)), sub_var=key)

            self.data[key] = value

    def get(self, sub_var):
        if sub_var in self.data:
            return self.data[sub_var]
        elif sub_var is None:
            raise KeyError(
                "Variable has sub-values; one must be requested explicitly.")
        else:
            raise KeyError("Unknown sub_var: '{}'".format(sub_var))

    def __repr__(self):
        return "<SubVariable({}) {}>".format(id(self.data), self.data)

    def __deepcopy__(self, memodict=None):
        sub_var = SubVariable()
        sub_var.data = copy.deepcopy(self.data)
        return sub_var

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
