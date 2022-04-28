from pavilion import create_files
from pavilion import plugins
from pavilion import variables
from pavilion.exceptions import TestConfigError
from pavilion.unittest import PavTestCase


class CreateFileTests(PavTestCase):
    """Test create_file and template functions."""

    def setUp(self) -> None:
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self) -> None:
        plugins._reset_plugins()

    def test_create_file(self):
        """Ensure runtime file creation is working correctly."""

        cf_out = self.pav_cfg.working_dir/'create_files_tests'

        create_files.create_file('cf1.txt', cf_out,
                                 ['Hello world', 'over and out'])

        create_files.create_file('cf2.txt', cf_out,
                                 ['Hello world', 'over and out'],
                                 newlines='')

        for fn in 'cf1.txt', 'cf2.txt':
            test_fn = cf_out/fn
            std_fn = self.TEST_DATA_ROOT/'create_files_results'/fn
            with test_fn.open() as test_file, std_fn.open() as std_file:
                self.assertEqual(test_file.read(), std_file.read())

        # Test path problems.
        for bad_path in '../../foo.txt', '/tmp/blah':
            with self.assertRaises(TestConfigError):
                create_files.create_file(bad_path, cf_out, ['Nothing important'])

    def test_resolve_template(self):
        """Check that template resolution works as expected."""

        var_man = variables.VariableSetManager()
        var_man.add_var_set('var', {'var1': 'val1'})

        expected_lines = [
            'Hiya!\n',
            'Resolve this val1.\n',
            '\n',
            'No trailing newline..',
        ]

        lines = create_files.resolve_template(self.pav_cfg, 'tmpl_test.pav', var_man)
        self.assertEqual(lines, expected_lines)

        for i in 1, 2, 3, 4, 5:
            bad_tmpl = 'tmpl_bad{}.pav'.format(i)
            with self.assertRaises(TestConfigError):
                create_files.resolve_template(self.pav_cfg, bad_tmpl, var_man)
