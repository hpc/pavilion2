####################################################################
#
#  Disclaimer and Notice of Copyright
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC.
#  This software was produced under U.S. Government contract
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL),
#  which is operated by Los Alamos National Security, LLC for
#  the U.S. Department of Energy. The U.S. Government has rights
#  to use, reproduce, and distribute this software.  NEITHER
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to
#  produce derivative works, such modified software should be
#  clearly marked, so as not to confuse it with the version
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary
#  forms, with or without modification, are permitted provided
#  that the following conditions are met:
#  -  Redistributions of source code must retain the
#     above copyright notice, this list of conditions
#     and the following disclaimer.
#  -  Redistributions in binary form must reproduce the
#     above copyright notice, this list of conditions
#     and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#  -  Neither the name of Los Alamos National Security, LLC,
#     Los Alamos National Laboratory, LANL, the U.S. Government,
#     nor the names of its contributors may be used to endorse
#     or promote products derived from this software without
#     specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
#  OF SUCH DAMAGE.
#
#  ###################################################################

# This module contains functions and classes for building variable sets for string insertion.
# There are three layers to every variable:
#   - A list of variable values
#   - A dictionary of sub-keys
#   - The values of those sub keys.
#   ie: [{key:value},...]
#
# From the user perspective, however, all but the value itself is optional.
#
# While variables are stored in this manner, these layers are automatically resolved in the
# trivial cases such as when there is only one element, or a single value instead of a set of
# key/value pairs.
#
# There are expected to be multiple variable sets; plain variables (var), permutations (per),
# plugin provided via 'sys', core pavilion provided (pav), and scheduler provided (sched).
#

from __future__ import print_function, unicode_literals, division


class VariableError(ValueError):
    """This error should be thrown when processing variable data, and something goes wrong."""

    def __init__(self, message, var_set=None, var=None, index=None, sub_var=None):
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

        return "Error processing variable key '{}': {}".format(key, self.base_message)


class VariableSetManager:
    """This class manages the various sets of variables, provides complex key based lookups,
    manages conflict resolution, and so on."""

    # The variable sets, in order of resolution.
    VAR_SETS = ('per', 'var', 'sys', 'pav', 'sched')

    def __init__(self):
        """Initialize the var set manager."""

        self.variable_sets = {}

        self.reserved_keys = []
        self.reserved_keys.extend(self.VAR_SETS)

    def add_var_set(self, name, value_dict):
        """Add a new variable set to this variable set manager. Variables in the set can then
        be retrieved by complex key.
        :param unicode name: The name of the var set. Must be one of the reserved keys.
        :param dict value_dict: A dictionary of values to populate the var set.
        :return: None
        :raises VariableError: On problems with the name or data.
        """
        if name not in self.reserved_keys:
            raise ValueError("Unknown variable set name: '{}'".format(name))

        if name in self.variable_sets:
            raise ValueError("Variable set '{}' already initialized.".format(name))

        try:
            var_set = VariableSet(name, self.reserved_keys, value_dict=value_dict)
        except VariableError as err:
            # Update the error to include the var set.
            err.var_set = name
            raise err

        self.variable_sets[name] = var_set

    def get_permutations(self, used_per_vars):
        """For every combination of permutation variables (that were used), return a new
        varset manager.
        :param set used_per_vars: A list of permutation variable names that were used.
        :return:
        """

        # Get every a dictionary of var:idx for every combination of used permutation variables.
        permutations = [{}]
        for per_var in used_per_vars:
            new_perms = []

            for old_perm in permutations:
                for i in range(self.len('per', per_var)):
                    new_perm = old_perm.copy()
                    new_perm[per_var] = i
                    new_perms.append(new_perm)

            permutations = new_perms

        permuted_var_mans = []

        if len(permutations) == 1:
            return [self]

        # Create a new var set manager for each permutation.
        for perm in permutations:
            var_man = VariableSetManager()

            var_man.variable_sets = self.variable_sets.copy()

            perm_var_set = VariableSet('per', self.reserved_keys)
            for var, idx in perm.items():
                new_list = [self.variable_sets['per'].data[var].data[idx]]
                vlist = VariableList()
                vlist.data = new_list

                perm_var_set.data[var] = vlist

            var_man.variable_sets['per'] = perm_var_set
            permuted_var_mans.append(var_man)

        return permuted_var_mans

    @classmethod
    def parse_key(cls, key):
        """Parse the given complex key, and return a reasonable (var_set, var, index, sub_var) tuple.
        :param Union(unicode,list,tuple) key: A 1-4 part key. These may either be given as a
            list/tuple of strings, or dot separated in a string. The components are var_set, var,
            index, and sub_var. Var is required, the rest are optional. Index is expected to be an
            integer, and var_set is expected to be a key category.
        :raises KeyError: For bad keys.
        :raises TypeError: When the key isn't a string.
        :returns: A (var_set, var, index, sub_var) tuple. Any component except var may be None.
        """

        if isinstance(key, list) or isinstance(key, tuple):
            parts = list(key)
        elif isinstance(key, unicode):
            parts = key.split('.')
        else:
            raise TypeError("Only unicode keys or tuples/lists are allowed.")

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
                # Note: The index is optional. This is for when it's given as an empty string.
                raise KeyError("Invalid, empty index in key: '{}'".format(key))
            else:
                try:
                    index = int(parts[0])
                    parts.pop(0)
                except ValueError:
                    # If it's not an integer, assume it's a sub_key.
                    pass

        sub_var = None
        if parts:
            sub_var = parts.pop(0)

            if sub_var == '':
                raise KeyError("Invalid, empty sub_var in key: '{}'".format(key))

        if parts:
            raise KeyError("Variable reference ({}) has too many parts, or an invalid "
                           "variable set (should be one of {})".format(key, cls.VAR_SETS))

        return var_set, var, index, sub_var

    def resolve_key(self, key):
        """Resolve the given key using this known var sets. Unlike parse_key, the var_set returned
        will never be None, as the key must correspond to a found variable in a var_set. In case of
        conflicts, the var_set will be resolved in order.
        :param Union(unicode,list,tuple) key: A 1-4 part key. These may either be given as a
        list/tuple of strings, or dot separated in a string. The components are var_set, var,
        index, and sub_var. Var is required, the rest are optional. Index is expected to be an
        integer, and var_set is expected to be a key category.
        :raises KeyError: For bad keys, and when the var_set can't be found.
        :returns: A tuple of (var_set, var, index, sub_var), index and sub_var may be None.
        """

        var_set, var, index, sub_var = self.parse_key(key)

        # If we didn't get an explicit var_set, find the first matching one with the given var.
        if var_set is None:
            for vs in self.reserved_keys:
                if vs in self.variable_sets and var in self.variable_sets[vs]:
                    var_set = vs
                    break

        if var_set is None:
            raise KeyError("Could not find a variable named '{}' in any variable set."
                           .format(var))

        return var_set, var, index, sub_var

    def __getitem__(self, key):
        """Find the item that corresponds to the given complex key.
        :param Union(unicode, list, tuple) key: A variable key. See parse_key for more.
        :return: The value for the given key.
        :raises KeyError: If the key value can't be found.
        """

        var_set, var, index, sub_var = self.resolve_key(key)

        # If anything else goes wrong, this will throw a KeyError
        try:
            return self.variable_sets[var_set].get(var, index, sub_var)
        except KeyError as msg:
            # Make sure our error message gives the full key.
            raise KeyError("Could not resolve reference '{}': {}".format(key, msg))

    def getlist(self, var_set, var):
        """Get the list of values for a given key. These values will always be a dictionary; If the
        the variable is simple (does not have sub_vars), the value will be in the 'None' key.
        :param unicode var_set: The var set to fetch from.
        :param unicode var: The variable to fetch.
        :return: A a list of the corresponding values/subvalues.
        :raises KeyError: If either the var_set or var don't exist.
        """

        if var_set not in self.variable_sets:
            raise KeyError("Unknown variable set '{}'".format(var_set, var))

        _var_set = self.variable_sets[var_set]

        if var not in self.variable_sets[var_set].data:
            raise KeyError("Variable set '{}' does not contain a variable named '{}'"
                           .format(var_set, var))

        var_list = _var_set.data[var]

        values = []
        for value in var_list:
            values.append(value.data)

        return values

    def len(self, var_set, var):
        """
        Get the length of the given key.
        :param unicode var_set: The var set to fetch from.
        :param unicode var: The variable to fetch.
        :return: The number of items in the found 'var_set.var', the index and sub_var are ignored.
        :raises KeyError: When the key has problems, or can't be found.
        """

        if var_set not in self.variable_sets:
            raise KeyError("Unknown variable set '{}'".format(var_set, var))

        _var_set = self.variable_sets[var_set]

        if var not in self.variable_sets[var_set].data:
            raise KeyError("Variable set '{}' does not contain a variable named '{}'"
                           .format(var_set, var))

        return len(_var_set.data[var])


class VariableSet:
    """A set of of variables. Essentially a wrapper around a mapping of var names to VariableList
    objects."""

    def __init__(self, name, reserved_keys, value_dict=None):
        """Initialize the VariableSet. The data can be set directly by assigning to .data,
        or from a config with the 'init_from_config' method.
        :param name: The name of this var set.
        :param reserved_keys: The list of reserved keys. Needed to check the given var names.
        :param value_dict: A mapping of var names to strings (unicode), a list of strings,
        a dict of strings, or a list of dict of strings.
        """

        self.data = {}
        self.name = name
        reserved_keys = reserved_keys

        if value_dict is not None:
            self._init_from_config(reserved_keys, value_dict)

    def _init_from_config(self, reserved_keys, value_dict):
        """Initialize the variable set from a config dictionary.
        :param value_dict: A mapping of var names to strings (unicode), a list of strings,
        a dict of strings, or a list of dict of strings.
        """

        for key, value in value_dict.items():
            if key in reserved_keys:
                raise VariableError("Var name '{}' is reserved.".format(key),
                                    var=key)

            try:
                self.data[key] = VariableList(values=value)
            except VariableError as err:
                err.var = key
                raise err

    def get(self, var, index, sub_var):
        """Return the value of the var given the var name, index, and sub_var name."""

        if var in self.data:
            return self.data[var].get(index, sub_var)
        else:
            raise KeyError("Variable set '{}' does not contain a variable named '{}'"
                           .format(self.name, var))

    def __contains__(self, item):
        return item in self.data


class VariableList:
    """Wraps a list of SubVariable objects. Even variables with a single value end up as a list (
    of one)."""

    def __init__(self, values=None):
        """Initialize the Varialbe list.
        :param values: A list of strings (unicode) or dicts of strings. The dicts must have the
        same keys.
        """

        self.data = []

        if values is not None:
            self._init_from_config(values)

    def _init_from_config(self, values):
        """Initialize the variable list from the given config values.
        :param values: A list of strings (unicode) or dicts of strings. The dicts must have the
        same keys.
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
                raise VariableError("Sub-keys do no match across variable values.",
                                    index=unicode(idx))

            try:
                self.data.append(SubVariable(value_pairs))
            except VariableError as err:
                err.index = unicode(idx)
                raise err

    def get(self, index, sub_var):
        """Return the variable value at the given index and sub_var."""

        if index is None:
            index = 0
        else:
            try:
                index = int(index)
            except ValueError:
                raise KeyError("Non-integer index given: '{}'".format(index))

        if index >= len(self.data) or index < -len(self.data):
            raise KeyError("Index out of range. There are only {} items in this variable."
                           .format(len(self.data)))

        return self.data[index].get(sub_var)

    def __len__(self):
        return len(self.data)


class SubVariable:
    """The final variable tier. Variables with no sub-var end up with a dict with a single
    None: value pair."""

    def __init__(self, value_pairs=None):
        """Initialize the sub_variable.
        :param dict value_pairs: The value of the sub_variable, via a configuration.
        """

        self.data = {}

        if value_pairs is not None:
            self._init_from_config(value_pairs)

    def _init_from_config(self, value_pairs):
        for key, value in value_pairs.items():
            if not isinstance(value, unicode):
                raise VariableError("Variable values must be unicode strings, got '{}'"
                                    .format(type(value)), sub_var=key)

            self.data[key] = value

    def get(self, sub_var):
        if sub_var in self.data:
            return self.data[sub_var]
        elif sub_var is None:
            raise KeyError("Variable has sub-values; one must be requested explicitly.")
        else:
            raise KeyError("Unknown sub_var: '{}'".format(sub_var))
