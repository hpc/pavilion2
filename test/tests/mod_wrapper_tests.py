from pavilion.unittest import PavTestCase
import unittest
import subprocess
from pathlib import Path
from pavilion.status_file import STATES
from pavilion import plugins


MODULE_SYSTEM_ROOT_PATHS = [
    Path('/usr/share/Modules'),
    Path('/usr/share/modules'),
    Path('/usr/share/lmod'),
]


def find_module_init():
    """Find the bash init file for a locally installed module system."""

    for path in MODULE_SYSTEM_ROOT_PATHS:
        if not path.exists():
            continue

        # Some installs are directly into one of these paths.
        no_subdir_path = path/'init'/'bash'
        if no_subdir_path.exists():
            return no_subdir_path

        # Others are in a versioned subdirectory. We don't have a way to
        # pick the 'correct' one if multiple exist, so we just grab the first
        # that works.
        for file in path.iterdir():
            init_file = file/'init'/'bash'
            if init_file.exists():
                return init_file

    return None


def has_module_cmd():
    """Return whether we can find a module command."""

    # Both LMod and Environment Modules (tmod) define a module
    # shell function.
    cmd = [
        '/bin/bash',
        '-c',
        'declare -F'
    ]
    functions = subprocess.check_output(cmd).decode('utf8')
    for line in functions.split('\n'):
        if 'module' in line.split():
            return True

    return False


class ModWrapperTests(PavTestCase):
    """Check the module add/remove/swap commands in run/build scripts against
    the local module system."""

    def _quick_test_cfg(self):
        """Return a test config with a module system set up added
        to the preamble."""

        test_cfg = super()._quick_test_cfg()

        preamble = []
        if not has_module_cmd():
            module_init = find_module_init()
            if module_init is not None:
                preamble.append(
                    'source {}'.format(find_module_init())
                )
            else:
                self.fail("No module system to initialize")
        preamble.append('export MODULEPATH={}'
                        .format(self.TEST_DATA_ROOT/'modules'))
        test_cfg['run']['preamble'] = preamble
        return test_cfg

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    SORT_FUNC = '''function sort_mods {
    awk '{
        split($0, arr, ":");  # Split the values by :
        asort(arr);           # Sort the values
        for (i=1; i<length(arr); i++) {  # Arrays are indexed from 1
            printf "%s:", arr[i]
        }
        printf "%s", arr[length(arr)]
    }'
}'''

    @unittest.skipIf(not has_module_cmd() and find_module_init() is None,
                     "Could not find a module system.")
    def test_add_module(self):
        """Check that adding a module works."""

        test_cfg = self._quick_test_cfg()

        test_cfg['run']['modules'] = [
            'test_mod1/1.0',
            'test_mod1',      # Should load 1.1 as the default.
            'test_mod2',      # Un-versioned.
        ]
        test_cfg['run']['cmds'] = [
            self.SORT_FUNC,
            'mods_sorted=$(echo "${TEST_MODULE_NAME}" | sort_mods)',
            'vers_sorted=$(echo "${TEST_MODULE_VERSION}" | sort_mods)',
            'echo "mods_sorted ${mods_sorted}"',
            'echo "vers_sorted ${vers_sorted}"',
            # test_mod1 only gets added once (no dups)
            '[[ "${mods_sorted}" == "test_mod1:test_mod2" ]] || exit 1',
            # test_mod2 has no version (but the module file appends it anyway.)
            '[[ "${vers_sorted}" == "1.0:1.1:" ]] || '
            '[[ "${vers_sorted}" == "1.1::" ]] || exit 1'
        ]

        test = self._quick_test(test_cfg)
        run_result = test.run()

        self.assertEqual(run_result, 0)

    @unittest.skipIf(not has_module_cmd() and find_module_init() is None,
                     "Could not find a module system.")
    def test_remove_module(self):
        """Check that removing a module works."""

        test_cfg = self._quick_test_cfg()

        modules = [
            'test_mod1/1.0',
            'test_mod2',
            'test_mod3/5.0',
        ]

        # Load all the modules.
        for mod in modules:
            test_cfg['run']['preamble'].append(
                'module load {} || exit 1'.format(mod)
            )

        test_cfg['run']['modules'] = [
            '-test_mod1',
            '-test_mod2',      # Un-versioned.
            '-test_mod3/5.0',
            '-test_mod_no-exist',  # Non-existent modules are fine to unload.
        ]

        test_cfg['run']['cmds'] = [
            # test_mod1 only gets added once (no dups)
            self.SORT_FUNC,
            'mods_sorted=$(echo "${TEST_MODULE_NAME}" | sort_mods)',
            'vers_sorted=$(echo "${TEST_MODULE_VERSION}" | sort_mods)',
            # test_mod1 only gets added once (no dups)
            '[[ "${mods_sorted}" == "" ]] || exit 1',
            '[[ "${vers_sorted}" == "" ]] || exit 1'
        ]
        test_cfg['run']['verbose'] = 'true'

        test = self._quick_test(test_cfg)
        run_result = test.run()

        self.assertEqual(run_result, 0)

    @unittest.skipIf(not has_module_cmd() and find_module_init() is None,
                     "Could not find a module system.")
    def test_swap_module(self):
        """Check that module swaps work."""

        test_cfg = self._quick_test_cfg()

        for mod in ('test_mod1/1.0', 'test_mod3/5.0'):
            test_cfg['run']['preamble'].append(
                'module load {} || exit 1'.format(mod)
            )

        test_cfg['run']['modules'] = [
            'test_mod1->test_mod1',      # Should swap 1.0 for 1.1 (the default)
            'test_mod_no-exist->test_mod2',  # This will just perform a load.
            'test_mod3/5.0->test_mod3/4.0'
        ]

        test_cfg['run']['verbose'] = 'true'

        test_cfg['run']['cmds'] = [
            self.SORT_FUNC,
            'mods_sorted=$(echo ${TEST_MODULE_NAME} | sort_mods)',
            'vers_sorted=$(echo ${TEST_MODULE_VERSION} | sort_mods)',
            # test_mod1 only gets added once (no dups)
            '[[ "${mods_sorted}" = "test_mod1:test_mod2:test_mod3" ]] || '
            'exit 1',
            # test_mod2 has no version (but the module file appends it anyway.)
            '[[ "${vers_sorted}" = "1.1:4.0:" ]] || exit 1'
        ]

        test = self._quick_test(test_cfg)
        run_result = test.run()

        self.assertEqual(run_result, 0)

    @unittest.skipIf(not has_module_cmd() and find_module_init() is None,
                     "Could not find a module system.")
    def test_module_fail(self):
        """Check failure conditions for each of module load/swap/remove."""

        test_cfg = self._quick_test_cfg()

        test_cfg['run']['modules'] = [
            'test_mod_noexist'
        ]

        # Make sure we fail for a non-existent module.
        test = self._quick_test(test_cfg)
        test.run()
        self.assertTrue(test.status.has_state(STATES.ENV_FAILED))

        test_cfg['run']['modules'] = [
            'test_mod1',
            'test_mod1->test_mod1/5.0'  # No such module to switch to.
        ]

        test = self._quick_test(test_cfg)
        test.run()
        self.assertTrue(test.status.has_state(STATES.ENV_FAILED),
                        msg=(test.path/'run.log').open().read())

    @unittest.skipIf(not has_module_cmd() and find_module_init() is None,
                     "Could not find a module system.")
    def test_module_plugin(self):
        """Make sure module wrapper plugins work as expected."""

        test_cfg = self._quick_test_cfg()

        test_cfg['run']['preamble'].append('set -v')
        test_cfg['run']['modules'] = ['itsa']
        test_cfg['run']['cmds'] = [
            '[[ "${TEST_MODULE_NAME}" = "fake" ]] || exit 1',
            '[[ "${FAKE_VAR}" = "Itsa_real" ]] || exit 1',
        ]

        # Make sure we fail for a non-existent module.
        test = self._quick_test(test_cfg)
        test.run()
        self.assertEqual(test.status.current().state, STATES.RUN_DONE)

