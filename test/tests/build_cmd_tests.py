from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion.plugins.commands.run import RunCommand
from pavilion.status_file import STATES
import io


class BuildCmdTests(PavTestCase):
    """The build command is really just the run command in disguise, so
    we only need to test the unique arguments that it enables."""

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        build_cmd = commands.get_command('build')
        build_cmd.outfile = io.StringIO()
        build_cmd.errfile = build_cmd.outfile

    def tearDown(self):
        plugins._reset_plugins()

    def test_multi_build_only(self):
        """Make sure we can just build multiple simultanious builds on
        both the front-end and the nodes."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'build',
            '-H', 'this',
            'build_parallel'
        ])

        build_cmd = commands.get_command(args.command_name)  # type: RunCommand
        build_ret = build_cmd.run(self.pav_cfg, args)

        build_cmd.outfile.seek(0)
        self.assertEqual(build_ret, 0, msg=build_cmd.outfile.read())

        for test in build_cmd.last_tests:
            test.wait(timeout=5)

        # Make sure we actually built separate builds
        builds = [test.builder for test in build_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        for test in build_cmd.last_tests:
            self.assertEqual(test.status.current().state, STATES.BUILD_DONE,
                             msg='Test {} status: {}'
                                 .format(test.id, test.status.current()))

    def test_local_builds_only(self):
        """Make sure we can just build multiple simultanious builds on
        both the front-end and the nodes."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'build',
            '-H', 'this',
            '--local-builds-only',
            'build_parallel'
        ])

        build_cmd = commands.get_command(args.command_name)  # type: RunCommand
        build_ret = build_cmd.run(self.pav_cfg, args)

        build_cmd.outfile.seek(0)
        self.assertEqual(build_ret, 0, msg=build_cmd.outfile.read())

        for test in build_cmd.last_tests:
            test.wait(timeout=10)

        # Make sure we actually built separate builds
        builds = [test.builder for test in build_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 2)

        for test in build_cmd.last_tests:
            self.assertEqual(test.status.current().state, STATES.BUILD_DONE,
                             msg='Test {} status: {}'
                             .format(test.id, test.status.current()))

    def test_rebuilds(self):
        """Make sure rebuilding works as expected."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'build',
            '-H', 'this',
            'build_rebuild',
            '--rebuild',
        ])

        build_cmd = commands.get_command(args.command_name)  # type: RunCommand
        self.assertEqual(build_cmd.run(self.pav_cfg, args), 0)

        for test in build_cmd.last_tests:
            test.wait(timeout=3)

        # Make sure we actually built separate builds
        builds = [test.builder for test in build_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        result_matrix = {
            'local1': [STATES.BUILD_DONE, STATES.BUILD_REUSED],
            'local1a': [STATES.BUILD_REUSED, STATES.BUILD_DONE],
            'nodes1': [STATES.BUILD_REUSED, STATES.BUILD_DONE],
            'nodes1a': [STATES.BUILD_REUSED, STATES.BUILD_DONE],
            'local2': [STATES.BUILD_DONE],
            'nodes3': [STATES.BUILD_DONE],
        }
        orig_names = {}
        for test in build_cmd.last_tests:
            tname = test.name.split('.')[1]
            self.assertIn(test.status.current().state, result_matrix[tname],
                          msg='Test {} status: {}'
                          .format(test.name, test.status.current()))
            orig_names[test.name] = test.builder.name

        self.assertEqual(build_cmd.run(self.pav_cfg, args), 0)

        for test in build_cmd.last_tests:
            test.wait(timeout=3)

        # Make sure we actually built separate builds
        builds = [test.builder for test in build_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        for test in build_cmd.last_tests:
            test.load_attributes()
            expected_name = orig_names[test.name] + '-2'
            self.assertEqual(test.build_name, expected_name,
                             msg=test.name)

            origin = test.build_origin_path.resolve().name
            self.assertEqual(origin, expected_name,
                             msg=test.name)

    def test_build_verbosity(self):
        """Make sure that the build verbosity levels at least appear to work."""

        arg_parser = arguments.get_parser()
        arg_sets = [
            ['build', '-H', 'this', '-l', '-b', 'build_parallel'],
            ['build', '-H', 'this', '-l', '-b', '-b', 'build_parallel'],
        ]
        build_cmd = commands.get_command('build')  # type: BuildCmd

        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)

            build_ret = build_cmd.run(self.pav_cfg, args)

            build_cmd.outfile.seek(0)
            self.assertEqual(build_ret, 0, msg=build_cmd.outfile.read())
