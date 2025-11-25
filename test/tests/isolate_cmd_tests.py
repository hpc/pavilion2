import tempfile
from pathlib import Path

from pavilion import commands
from pavilion import arguments
from pavilion.unittest import PavTestCase


class IsolateCmdTests(PavTestCase):

    def test_no_archive(self):
        run_cmd = commands.get_command("run")
        isolate_cmd = commands.get_command("isolate")

        run_cmd.silence()
        isolate_cmd.silence()

        parser = arguments.get_parser()
        run_args = ["run", "-H", "this", "hello_world.hello"]

        run_cmd.run(self.pav_cfg, parser.parse_args(run_args))
        last_test = next(iter(run_cmd.last_tests))

        with tempfile.TemporaryDirectory() as dir:
            isolate_args = parser.parse_args(["isolate", str(Path(dir) / "dest")])

            self.assertEqual(isolate_cmd.run(self.pav_cfg, isolate_args), 0)

            source_files = set(map(lambda x: x.name, last_test.path.listdir()))
            dest_files = set(map(lambda x: x.name, (Path(dir) / "dest").listdir()))

            self.assertEqual(source_files, dest_files)

    def test_zip_arcive(self):
        ...