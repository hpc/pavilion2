
"""This module contains functions and classes for building variable sets for
string insertion.

There are three layers to every variable:

- A list of variable values
- A dictionary of sub-keys
- The values of those sub keys.
  ie: [{key:value},...]

From the user perspective, however, all but the value itself is optional.

While variables are stored in this manner, these layers are automatically
resolved in the trivial cases such as when there is only one element, or a
single value instead of a set of key/value pairs.

There are expected to be multiple variable sets: plain variables (var),
plugin provided via sys_vars (sys), core pavilion provided (pav), and scheduler
provided (sched).
"""

import copy
import json
from typing import Union

from . import parsers


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


class DeferredError(VariableError):
    """Raised when we encounter a deferred variable we can't resolve."""


class DeferredVariable:
    """The value for some variables may not be available until a test is
actually running. Deferred variables act as a placeholder in such
circumstances, and output an escape sequence when converted to a str.
"""

    # NOTE: Other than __init__, this should always have the same interface
    # as VariableList.

    def get(self, index, sub_var):      # pylint: disable=no-self-use
        """Deferred variables should never have their value retrieved."""

        # This should always be caught before this point.
        raise RuntimeError(
            "Attempted to get the value of a deferred variable."
        )

    def __len__(self):
        """Deferred variables always have a single value."""

        # This should always be caught before this point.
        raise RuntimeError(
            "Attempted to get the length of a deferred variable."
        )


class VariableSetManager:
    """This class manages the various sets of variables, provides complex key
based lookups, manages conflict resolution, and so on. Anything that works
with pavilion variables should do so through an instance of this class.

Usage: ::

    var_man = VariableSetManager()
    # pav_vars and sys_vars should be dictionary like objects
    var_man.add_var_set('sys', sys_vars)
    var_man.add_var_set('pav', pav_vars)

    var_man['sys.sys_name']
    var_man['sys_name']
"""

    # The variable sets, in order of resolution.
    VAR_SETS = ('var', 'sys', 'pav', 'sched')

    def __init__(self):
        """Initialize the var set manager."""

        self.variable_sets = {}

        self.reserved_keys = []
        self.reserved_keys.extend(self.VAR_SETS)

        # A dictionary of the known deferred variables.
        self.deferred = set()

    def add_var_set(self, name, value_dict):
        """Add a new variable set to this variable set manager. Variables in
        the set can then be retrieved by complex key.

        :param str name: The name of the var set. Must be one of the reserved
            keys.
        :param Union(dict,collections.UserDict) value_dict: A dictionary of
            values to populate the var set.
        :return: None
        :raises VariableError: On problems with the name or data.
        """
        if name not in self.reserved_keys:
            raise ValueError("Unknown variable set name: '{}'".format(name))

        if name in self.variable_sets:
            raise ValueError(
                "Variable set '{}' already initialized.".format(name))

        try:
            var_set = VariableSet(name, value_dict=value_dict)
        except VariableError as err:
            # Update the error to include the var set.
            err.var_set = name
            raise err

        for var, val in var_set.data.items():
            if isinstance(val, DeferredVariable):
                self.set_deferred(name, var)

        self.variable_sets[name] = var_set

    def get_permutations(self, used_per_vars):
        """For every combination of permutation variables (that were used),
return a new var_set manager that contains only a single value
(possibly a complex one) for each permutation var, in every possible
permutation.

:param list[(str, str)] used_per_vars: A set of permutation variable names that
    were used, as a tuple of (var_set, var_name).
:return: A list of permuted variable managers.
:rtype: VariableSetManager
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
            var_man = copy.deepcopy(self)

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
            var_set = parts.pop(0)

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
                    # This denotes that all values should be returned.
                    if parts[0] == '*':
                        index = '*'
                    else:
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

    def resolve_references(self):
        """Resolve all variable references that are within variable values
        defined in the 'variables' section of the test config.

        :raises TestConfigError: When reference loops are found.
        :raises KeyError: When an unknown variable is referenced.
        """

        # We only want to resolve variable references in the variable section
        var_vars = self.variable_sets['var']
        unresolved_vars = {}
        parser = parsers.strings.get_string_parser()
        var_visitor = parsers.strings.StringVarRefVisitor()
        transformer = parsers.StringTransformer(self)

        # Find all the variable value strings that reference variables
        for var, var_list in var_vars.data.items():
            # val is a list of dictionaries

            for idx in range(len(var_list.data)):
                sub_var = var_list.data[idx]
                for key, val in sub_var.data.items():
                    tree = parser.parse(val)
                    variables = var_visitor.visit(tree)

                    if variables:
                        # Unresolved variable reference that will be resolved
                        # below.
                        unresolved_vars[('var', var, idx, key)] = (tree,
                                                                   variables)

        # unresolved variables form a tree where the leaves should all be
        # resolved variables. This iteratively finds unresolved variables whose
        # references are resolved and resolves them. This should collapse the
        # tree until there are no unresolved variables left.
        while unresolved_vars:
            did_resolve = False
            for uvar, (tree, variables) in unresolved_vars.copy().items():
                for var_str in variables:
                    var_key = self.resolve_key(var_str)
                    # Set the index 0 if it is None
                    if var_key[2] == '*':
                        # If the var references a whole list of items,
                        # make sure all are resolved.
                        if [key for key in unresolved_vars
                                if (key[:2], key[3]) ==
                                    (var_key[:2], var_key[3])]:
                            break
                    else:
                        if var_key[2] is None:
                            var_key = (var_key[0], var_key[1], 0, var_key[3])

                        if var_key in unresolved_vars:
                            break
                else:
                    # All variables referenced in uvar are resolvable
                    var_set, var_name, index, sub_var = uvar

                    try:
                        res_val = transformer.transform(tree)
                    except DeferredError:
                        res_val = None

                    if res_val is None:
                        # One or more of the variables is deferred, so we can't
                        # resolve this now. Mark it as deferred.
                        self.set_deferred(var_set, var_name, index, sub_var)
                    else:
                        # Otherwise, save the resolved value.
                        self._set_value((var_set, var_name, index, sub_var),
                                        res_val)

                    del unresolved_vars[uvar]
                    did_resolve = True

            # If no variable is resolved in this iteration, then all remaining
            # unresolved variables are part of a variable reference loop and
            # therefore cannot eventually be resolved.
            if not did_resolve:
                raise VariableError(
                    "Variables '{}' contained reference loop"
                    .format([k[1] for k in unresolved_vars.keys()]))

    def __getitem__(self, key):
        """Find the item that corresponds to the given complex key.
        :param Union(str, list, tuple) key: A variable key. See parse_key for
            more.
        :return: The value for the given key.
        :raises KeyError: If the key value can't be found.
        """

        var_set, var, index, sub_var = key_parts = self.resolve_key(key)

        if self.is_deferred(key_parts):
            raise DeferredError("Trying to get the value of a deferred "
                                "variable.")

        # If anything else goes wrong, this will throw a KeyError
        try:
            return self.variable_sets[var_set].get(var, index, sub_var)
        except KeyError as msg:
            # Make sure our error message gives the full key.
            raise KeyError(
                "Could not resolve reference '{}': {}"
                .format(self.key_as_dotted(key), msg.args[0]))

    def get(self, key: str, default=None) -> str:
        """Get an item, or the provided default, as per dict.get. """

        try:
            return self[key]
        except KeyError:
            return default

    def _set_value(self, key, value):
        """Set the value at 'key' to the new value. A value must already
        exist at this location."""

        var_set, var, index, sub_var = self.resolve_key(key)

        self.variable_sets[var_set].set_value(var, index, sub_var, value)

    def set_deferred(self, var_set, var, idx=None, sub_var=None):
        """Set the given variable as deferred. Variables may be deferred
        as a whole, or as individual list or sub_var items.

        :param str var_set: The var_set of the deferred var.
        :param str var: The variable name.
        :param Union(int, None) idx: The idx of the deferred var. If set to
            None, the variable is deferred for all indexes. Note that single
            valued variables have an index of zero.
        :param Union(str, None) sub_var: The sub_variable name that is
            deferred.
        """

        # There are three cases in what a deferred variable record may look
        # like:
        #
        # 1. (var_set, var, None, None) - A single (simple) valued variable or
        #    a generally deferred variable (like from sys or sched).
        # 2. (var_set, var, #, None) - A specific simple valued variable.
        # 3. (var_set, var, #, sub_var) - A specific subvar.

        # Note there is no case where you have a subvar but not an index.
        if idx is None and sub_var is not None:
            idx = 0

        self.deferred.add((var_set, var, idx, sub_var))

    def is_deferred(self, key):
        """Return whether the given variable is deferred. Fully specified
        variables (with idx and sub_var set) may be deferred specifically
        or in general at various levels.

        :rtype: bool
        """

        var_set, var, idx, sub_var = self.resolve_key(key)
        # When the idx is None, check generally and against index 0.
        if idx is None:
            idx = 0

        # See set_deferred for the cases...
        return (
            # This is generally deferred
            (var_set, var, None, None) in self.deferred or
            # A specific simple value.
            (var_set, var, idx, None) in self.deferred or
            # A specific sub-value.
            (var_set, var, idx, sub_var) in self.deferred)

    def any_deferred(self, key: Union[str, tuple]) -> bool:
        """Return whether any members of the given variable are deferred."""

        var_set, var, _, _ = self.resolve_key(key)

        all_def_vars = [dkey[:2] for dkey in self.deferred]

        return (var_set, var) in all_def_vars

    def len(self, var_set, var):
        """Get the length of the given key.

        :param str var_set: The var set to fetch from.
        :param str var: The variable to fetch.
        :rtype: int
        :return: The number of items in the found 'var_set.var'.
        :raises KeyError: When the key has problems, or can't be found.
        """

        if self.is_deferred((var_set, var, None, None)):
            raise DeferredError(
                "Trying to get the length of deferred variable '{}'"
                .format('.'.join([var_set, var])))

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

    def as_dict(self):
        """Return the all variable sets as a single dictionary. This will
        be structured as the config data is expected to be received.
        (A dict of variables where the values are lists of either structs
        or string values).

        :rtype: dict
        """

        dvar_sets = {}

        for var_set in self.variable_sets.values():
            dvar_sets[var_set.name] = {}

            for var_name in var_set.data.keys():
                dvar_sets[var_set.name][var_name] = dvar_set = []
                item = var_set.data[var_name]

                if isinstance(item, DeferredVariable):
                    dvar_sets[var_name] = None
                else:
                    for subitem in item.data:
                        if None in subitem.data:
                            dvar_set.append(subitem.data[None])
                        else:
                            dvar_set.append(subitem.data)
        return dvar_sets

    def save(self, path):
        """Save the variable set to the given stream as JSON.

        :param pathlib.Path path: The file path to write to.
        """

        try:
            with path.open('w') as outfile:
                data = self.as_dict()
                # Save our set of deferred variables too.
                data['__deferred'] = list(self.deferred)

                json.dump(data, outfile)
        except (OSError, IOError, FileNotFoundError) as err:
            raise VariableError(
                "Could not write variable file at '{}': {}"
                .format(path, err.args[0])
            )

    @classmethod
    def load(cls, path):
        """Load a saved variable set.

        :param pathlib.Path path: The variable file to load.

        """

        try:
            with path.open() as stream:
                data = json.load(stream)
        except (json.decoder.JSONDecodeError, IOError, FileNotFoundError) \
                as err:
            raise \
                RuntimeError(
                    "Could not load variable file '{}': {}"
                    .format(path, err.args[0]))

        var_man = cls()

        var_man.deferred = set([tuple(k) for k in data['__deferred']])
        del data['__deferred']

        for var_set_name, var_set_vars in data.items():

            # Get a list of all top level deferred variables for this var_set,
            # and then make them into deferred var objects.
            deferred = [
                dfr_name
                for dfr_set, dfr_name, dfr_idx, dfr_subvar in var_man.deferred
                if (dfr_set, dfr_idx, dfr_subvar) == (var_set_name, None, None)
            ]
            for dvar_name in deferred:
                var_set_vars[dvar_name] = DeferredVariable()

            var_man.variable_sets[var_set_name] = VariableSet(
                name=var_set_name,
                value_dict=var_set_vars,
            )

        return var_man

    def undefer(self, new_vars):
        """Get non-deferred values for all the deferred values in
        this variable set, leaving the non-deferred values intact.

        :param VariableSetManager new_vars: A completely non-deferred
            variable set manager.
        """

        # There are a lot of assumptions in here about what variables exist
        # in new_vars. new_vars should have a value for every variable in
        # self, because it should be from the same pavilion instance, with
        # the same config, and the same test config. Crazy stuff can happen
        # though, like people removing plugins between when a test starts
        # and when it runs.

        # Get values for all the top level deferred variables.
        for d_var_set, d_var, d_idx, d_subvar in self.deferred.copy():
            if not (d_idx is None and d_subvar is None):
                # Skip the fine-grained deferred variables ( all of which
                # should be in the 'var' variable set).
                continue

            # Replace the old value with the new.
            var_set = self.variable_sets[d_var_set]
            var_set.data[d_var] = new_vars.variable_sets[d_var_set].data[d_var]

            # Remove this variable from or set of deferred.
            self.deferred.remove((d_var_set, d_var, d_idx, d_subvar))

        # Now we have to go through the very specifically deferred variables
        # (an artifact of when we resolved variable value references)
        # and resolve them. This will look a lot like resolve_references

        while self.deferred:
            resolved_any = False
            for def_key in self.deferred.copy():
                var_set, var, index, sub_var = def_key
                def_val = self.variable_sets[var_set].get(var, index, sub_var)

                try:
                    resolved = parsers.parse_text(def_val, self)
                except DeferredError:
                    continue

                self._set_value(def_key, resolved)
                self.deferred.remove(def_key)
                resolved_any = True

            if not resolved_any:
                raise VariableError(
                    "Reference loop in variable resolution for variables: {}."
                    .format(list(self.deferred))
                )

    def __deepcopy__(self, memodict=None):
        """Deeply copy this variable set manager."""

        var_man = VariableSetManager()

        var_man.variable_sets = copy.deepcopy(self.variable_sets)
        var_man.deferred = copy.deepcopy(self.deferred)

        return var_man

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

    def __eq__(self, other):
        if not isinstance(other, VariableSetManager):
            raise ValueError("Can only compare variable set managers to each "
                             "other.")

        return self.as_dict() == other.as_dict()


class VariableSet:
    """A set of of variables. Essentially a wrapper around a mapping of var
names to VariableList objects."""

    def __init__(self, name, value_dict=None):
        """Initialize the VariableSet. The data can be set directly by
assigning to .data, or from a config with the 'init_from_config'
method.

:param str name: The name of this var set.
    given var names.
:param value_dict: A mapping of var names to strings (str), a list of
    strings, a dict of strings, or a list of dict of strings.
"""

        self.data = {}
        self.name = name

        if value_dict is not None:
            self._init_from_config(value_dict)

    def _init_from_config(self, value_dict):
        """Initialize the variable set from a config dictionary.

:param value_dict: A mapping of var names to strings (str), a list of
    strings, a dict of strings, or a list of dict of strings.
"""

        for key, value in value_dict.items():
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

    def set_value(self, var, index, sub_var, value):
        """Set the value at the given location to value."""

        self[var].set_value(index, sub_var, value)

    def __contains__(self, item):
        return item in self.data

    def __deepcopy__(self, memodict=None):
        variable_set = VariableSet(name=self.name)
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
        """Initialize the Variable list.

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
                    "Sub-keys do not match across variable values. "
                    "Idx {} had keys {}, but expected {}"
                    .format(idx, set(value_pairs.keys()), sub_vars),
                    index=str(idx))

            try:
                self.data.append(SubVariable(value_pairs))
            except VariableError as err:
                err.index = str(idx)
                raise err

    def get(self, index, sub_var):
        """Return the variable value at the given index and sub_var."""

        if index == '*':
            return [data.get(sub_var) for data in self.data]
        else:
            return self[index].get(sub_var)

    def set_value(self, index, sub_var, value):
        """Set the value at the given location to value."""

        self[index].set_value(sub_var, value)

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

        if len(self.data) == 0:
            raise KeyError('Variable is empty.')
        elif not -len(self.data) <= index < len(self.data):
            raise KeyError(
                "Index out of range. There are only {} items in this variable."
                .format(len(self.data)))

        return self.data[index]


class SubVariable:
    """The final variable tier. Variables with no sub-var end up with a
dict with a single None: value pair."""

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
                    "Variable values must be unicode strings, got '{}' as '{}'"
                    .format(value, type(value)), sub_var=key)

            self.data[key] = value

    def get(self, sub_var):
        """Gets the actual variable value."""

        if sub_var in self.data:
            return self.data[sub_var]
        elif sub_var is None:
            raise KeyError(
                "Variable has sub-values; one must be requested explicitly.")
        else:
            raise KeyError("Unknown sub_var: '{}'".format(sub_var))

    def set_value(self, sub_var, value):
        """Set the value at the given location to value."""

        self.data[sub_var] = value

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
