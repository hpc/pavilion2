"""Objects that wrap test configs that haven't been turned into Test Run's yet."""

import copy
import sys
from typing import List, Union, Dict, Tuple
import uuid

from pavilion.errors import TestConfigError, SchedulerPluginError, VariableError
from pavilion import resolve
from pavilion import variables
from pavilion import schedulers
from pavilion import parsers
from pavilion import output

from .request import TestRequest

class ProtoTest:
    """A fully resolved test config and associated information."""

    def __init__(self, request: TestRequest, config: Dict,
                 var_man: variables.VariableSetManager, count: int = 1):

        self.request = request
        self.config = config
        self.var_man = var_man
        self.count = count

    def update_config(self, new_config):
        """Replace the existing config with this new (probably completely resolved) version."""

        self.config = new_config

    def copy(self) -> 'ProtoTest':
        """Create a copy of this proto test."""

        ptest_copy = ProtoTest(request=self.request,
                               config=copy.deepcopy(self.config),
                               var_man=copy.deepcopy(self.var_man),
                               count=self.count)
        return ptest_copy

    def resolve(self) -> Dict:
        """Resolve all the strings in this test config. This mostly exists to consolidate
        error handling (we could call resolve.test_config directly)."""

        try:
            new_cfg = resolve.test_config(self.config, self.var_man)
            self.update_config(new_cfg)
            return new_cfg
        except TestConfigError as err:
            name = self.config['name']
            permute_on = self.config.get('permute_on')
            if permute_on:
                permute_values = {key: var_man.get(key) for key in permute_on}

                raise TestConfigError(
                    "Error resolving test {} with permute values:"
                    .format(name), err, data=permute_values, request=self.request)
            else:
                raise TestConfigError(
                    "Error resolving test {}".format(name), err, request=self.request)

class RawProtoTest:
    """An simple object that holds the pair of a test config and its variable
    manager."""

    def __init__(self, request: TestRequest, config: Dict, base_var_man: variables.VariableSetManager):
        """A partially initialized pavilion test config."""

        self.request: TestRequest = request
        self.config: Dict = config
        self.var_man: variables.VariableSetManager = None
        self.count = request.count

        user_vars = self.config.get('variables', {})
        base_var_man = copy.deepcopy(base_var_man)
        test_name = self.config.get('name', '<no name>')

        # Since per vars are the highest in resolution order, we can make things
        # a bit faster by adding these after we find the used per vars.
        try:
            base_var_man.add_var_set('var', user_vars)
        except VariableError as err:
            raise TestConfigError("Error in variables section for test '{}'"
                                  .format(test_name), err, request=self.request)

        self.var_man = base_var_man


    def check_variable_consistency(self):
        """Check all the variables defined as defaults with a null value to
        make sure they were actually defined, and that all sub-var dicts have consistent keys.


        :raises TestConfigError: When variable inconsistencies are found.
        """

        test_name = self.config.get('name', '<unnamed>')
        test_suite = self.config.get('suite_path', '<no suite>')

        for var_key, values in self.config.get('variables', {}).items():

            if not values:
                raise TestConfigError(
                    "In test '{}' from suite '{}', test variable '{}' was defined "
                    "but wasn't given a value."
                    .format(test_name, test_suite, var_key), request=self.request)

            first_value_keys = set(values[0].keys())
            for i, value in enumerate(values):
                for subkey, subval in value.items():
                    if subkey is None:
                        full_key = var_key
                    else:
                        full_key = '.'.join([var_key, subkey])

                    if subval is None:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has an empty "
                            "value. Empty defaults are fine (as long as they are "
                            "overridden), but regular variables should always be given "
                            "a value (even if it's just an empty string)."
                            .format(test_name, test_suite, full_key), request=self.request)

                value_keys = set(value.keys())
                if value_keys != first_value_keys:
                    if None in first_value_keys:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has  "
                            "inconsistent keys. The first value was a simple variable "
                            "with value '{}', while value {} had keys {}"
                            .format(test_name, test_suite, var_key, values[0][None], i + 1,
                                    value_keys), request=self.request)
                    elif None in value_keys:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has "
                            "inconsistent keys.The first value had keys {}, while value "
                            "{} was a simple value '{}'."
                            .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                    value[None]), request=self.request)
                    else:
                        raise TestConfigError(
                            "In test '{}' from suite '{}', test variable '{}' has "
                            "inconsistent keys. The first value had keys {}, "
                            "while value {} had keys {}"
                            .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                    value_keys), request=self.request)

                if not values:
                    raise TestConfigError(
                        "In test '{}' from suite '{}', test variable '{}' was defined "
                        "but wasn't given a value."
                        .format(test_name, test_suite, var_key), request=self.request)

                first_value_keys = set(values[0].keys())
                for i, value in enumerate(values):
                    for subkey, subval in value.items():
                        if subkey is None:
                            full_key = var_key
                        else:
                            full_key = '.'.join([var_key, subkey])

                        if subval is None:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has an empty "
                                "value. Empty defaults are fine (as long as they are "
                                "overridden), but regular variables should always be given "
                                "a value (even if it's just an empty string)."
                                .format(test_name, test_suite, full_key), request=self.request)

                    value_keys = set(value.keys())
                    if value_keys != first_value_keys:
                        if None in first_value_keys:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has  "
                                "inconsistent keys. The first value was a simple variable "
                                "with value '{}', while value {} had keys {}"
                                .format(test_name, test_suite, var_key, values[0][None], i + 1,
                                        value_keys), request=self.request)
                        elif None in value_keys:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has "
                                "inconsistent keys.The first value had keys {}, while value "
                                "{} was a simple value '{}'."
                                .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                        value[None]), request=self.request)
                        else:
                            raise TestConfigError(
                                "In test '{}' from suite '{}', test variable '{}' has "
                                "inconsistent keys. The first value had keys {}, "
                                "while value {} had keys {}"
                                .format(test_name, test_suite, var_key, first_value_keys, i + 1,
                                        value_keys), request=self.request)

    def resolve_permutations(self) -> List[ProtoTest]:
        """Resolve permutations for all used permutation variables, returning a
        variable manager for each permuted version of the test config. This requires that
        we incrementally apply permutations - permutation variables may contain references that
        refer to each other (or scheduler variables), so we have to resolve non-permuted
        variables, apply any permutations that are ready, and repeat until all are applied
        (taking a break to add scheduler variables when we can't proceed without them anymore).

        :returns: A list of ProtoTest objects.
        :raises TestConfigError: When there are problems with variables or the
            permutations.
        """

        debug = False

        permute_on = self.config['permute_on']
        self.config['permute_base'] = uuid.uuid4().hex

        used_per_vars = self._check_permute_vars(permute_on)
        self.config['subtitle'] = self._make_subtitle_template(used_per_vars)

        test_name = self.config.get('name', '<no name>')

        sched_name = self.config.get('scheduler')
        if sched_name is None:
            raise RuntimeError("No scheduler was given. This should only happen "
                               "when unit tests fail to define it.", request=self.request)
        try:
            sched = schedulers.get_plugin(sched_name)
        except SchedulerPluginError:
            raise TestConfigError("Could not find scheduler '{}' for test '{}'"
                                  .format(sched_name, test_name), request=self.request)
        if not sched.available():
            raise TestConfigError("Test {} requested scheduler {}, but it isn't "
                                  "available on this system.".format(test_name, sched_name),
                                  request=self.request)

        var_men = [self.var_man]
        # Keep trying to resolve variables and create permutations until we're out. This
        # iteratively takes care of any permutations that aren't self-referential and don't
        # depend on the scheduler variables.
        while True:
            # Resolve what references we can in variables, but refuse to resolve any based on
            # permute vars. (Note this does handle any recursive references properly)
            basic_per_vars = [var for var_set, var in used_per_vars if var_set == 'var']
            try:
                resolved, _ = self.var_man.resolve_references(partial=True,
                                                              skip_deps=basic_per_vars)
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (progressive).",
                                      err, request=self.request)

            # Convert to the same format as our per_vars
            resolved = [('var', var) for var in resolved]

            # Variables to permute on this iteration.
            permute_now = []
            for var_set, var in used_per_vars.copy():
                if var_set not in ('sched', 'var') or (var_set, var) in resolved:
                    permute_now.append((var_set, var))
                    used_per_vars.remove((var_set, var))

            # We've done all we can without resolving scheduler variables.
            if not permute_now:
                break

            # Get permutations for each existing variable manager.
            new_var_men = []
            for var_man in var_men:
                new_var_men.extend(var_man.get_permutations(permute_now))
            var_men = new_var_men

            if debug:
                output.fprint(sys.stderr, 'inc permutes, permuted on ', permute_now,
                              'got ', len(var_men))


        # Calculate permutations for variables that we 'could resolve' if not for the fact
        # that they are permutation variables. These are variables that refer to themselves
        # (either directly (a.b->a.c) or indirectly (a.b -> d -> a.c).
        all_var_men = []
        for var_man in var_men:
            basic_per_vars = [var for var_set, var in used_per_vars if var_set == 'var']
            try:
                _, could_resolve = var_man.resolve_references(partial=True,
                                                              skip_deps=basic_per_vars)
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (post-prog).",
                                      err, request=self.request)

            # Resolve permutations only for those 'could_resolve' variables that
            # we actually permute over.
            all_var_men.extend(var_man.get_permutations(
                [('var', var_name) for var_name in could_resolve
                 if var_name in could_resolve]))

            if debug:
                output.fprint(sys.stderr, 'tangled permutes, permuted on ', could_resolve,
                              'got ', len(var_men))
        var_men = all_var_men

        # Everything left at this point will require the sched vars to deal with.
        all_var_men = []
        for var_man in var_men:
            # Resolve the variables that don't depend sched, but have complicated relationships
            # we couldn't solve iteratively. If there's anything left at this point, it will
            # probably result in undesired behavior, but it's the best we can do.
            try:
                var_man.resolve_references(partial=True)
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (pre-sched).",
                                      err, request=self.request)

            sched_cfg = self.config.get('schedule', {})
            try:
                sched_cfg = resolve.test_config(sched_cfg, var_man)
            except KeyError as err:
                raise TestConfigError(
                    "Failed to resolve the scheduler config due to a missing or "
                    "unresolved variable for test {}".format(test_name),
                    err, request=self.request)

            try:
                sched_vars = sched.get_initial_vars(sched_cfg)
            except SchedulerPluginError as err:
                raise TestConfigError(
                    "Error getting initial variables from scheduler {} for test '{}'.\n\n"
                    "Scheduler Config: \n{}"
                    .format(sched_name, test_name, pprint.pformat(sched_cfg)),
                    err, request=self.request)

            var_man.add_var_set('sched', sched_vars)
            # Now we can really fully resolve all the variables.
            try:
                var_man.resolve_references()
            except VariableError as err:
                raise TestConfigError("Error resolving variable references (final).",
                                      err, request=self.request)

            # And do the rest of the permutations.
            all_var_men.extend(var_man.get_permutations(used_per_vars))

            if debug:
                output.fprint(sys.stderr, 'sched permutes, permuted on ', used_per_vars,
                              'got', len(all_var_men))

        return [ProtoTest(self.request, self.config, var_man, count=self.count)
                for var_man in all_var_men]

    def _check_permute_vars(self, permute_on) -> List[Tuple[str, str]]:
        """Check the permutation variables and report errors. Returns a set of the
        (var_set, var) tuples."""

        per_vars = set()
        for per_var in permute_on:
            try:
                var_set, var, index, subvar = self.var_man.resolve_key(per_var)
            except KeyError:
                # We expect to call this without adding scheduler variables first.
                if per_var.startswith('sched.') and '.' not in per_var:
                    per_vars.add(('sched', per_var))
                    continue
                else:
                    raise TestConfigError(
                        "Permutation variable '{}' is not defined. Note that if you're permuting "
                        "over a scheduler variable, you must specify the variable type "
                        "(ie 'sched.node_list')"
                        .format(per_var))
            if index is not None or subvar is not None:
                raise TestConfigError(
                    "Permutation variable '{}' contains index or subvar. "
                    "When giving a permutation variable only the variable name "
                    "and variable set (optional) are allowed. Ex: 'sys.foo' "
                    " or just 'foo'."
                    .format(per_var))
            elif self.var_man.any_deferred(per_var):
                raise TestConfigError(
                    "Permutation variable '{}' references a deferred variable "
                    "or one with deferred components."
                    .format(per_var))
            per_vars.add((var_set, var))

        return sorted(list(per_vars))

    def _make_subtitle_template(self, permute_vars) -> str:
        """Make an appropriate default subtitle given the permutation variables.

        :param permute_vars: The permutation vars, as returned by check_permute_vars.
        :param subtitle: The raw existing subtitle.
        :param var_man: The variable manager.
        """

        subtitle = self.config.get('subtitle')

        parts = []
        if permute_vars and subtitle is None:
            var_dict = self.var_man.as_dict()
            # These should already be sorted
            for var_set, var in permute_vars:
                if var_set == 'sched':
                    parts.append('{{sched.' + var + '}}')
                elif isinstance(var_dict[var_set][var][0], dict):
                    parts.append('_' + var + '_')
                else:
                    parts.append('{{' + var + '}}')

            return '-'.join(parts)
        else:
            return subtitle
