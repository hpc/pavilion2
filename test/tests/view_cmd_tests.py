"""Exercise the view command."""
import json

from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase


class ViewCmdTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.link_files(
            "suites/hello_world.yaml",
            "plugins/schedulers/dummy.*")

    def test_view(self):

        view_cmd = commands.get_command('view')
        view_cmd.silence()

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'view', 'hello_world'
        ])

        self.assertEqual(view_cmd.run(self.pav_cfg, args), 0)

    def test_view_json(self):
        """Test that the --json flag outputs valid JSON."""

        view_cmd = commands.get_command('view')
        view_cmd.silence()

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'view', '--json', 'hello_world'
        ])

        self.assertEqual(view_cmd.run(self.pav_cfg, args), 0)

        # Verify output is valid JSON
        output_str = view_cmd.outfile.getvalue()

        try:
            json_obj = json.loads(output_str)
        except json.JSONDecodeError as e:
            self.fail(f"Output is not valid JSON: {e}")

        print(json_obj)

        # Ensure it's a dict with expected structure (non-empty)
        self.assertIsInstance(json_obj, dict)
        self.assertTrue(json_obj != {})
