from argparse import ArgumentParser, Namespace
from pathlib import Path

from pavilion.config import PavConfig
from pavilion.scriptcomposer import ScriptComposer
from .base_classes import Command


class MakeActivateCommand(Command):
    """Make the 'activate' bash script."""

    def __init__(self):
        super().__init__(
            "make-activate",
            "Make the bash activation script.",
            short_help="Make activation script"
        )

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("dest", help="Location in which to save the script.", type=Path,
                            default=Path("."), nargs="?")
        parser.add_argument("-n", "--name", help="Name of the script", default="activate.sh")
        parser.add_argument("-c", "--config-dir", help="Config directory location", type=Path)
        parser.add_argument("-u", "--umask", help="Umask value to set in the script.",
                            default="002")

    def run(self, pav_cfg: PavConfig, args: Namespace) -> None:
        this_dir = Path(__file__).parent.resolve()
        pav_bin = this_dir.parents[2] / "bin"
        script_path = args.dest / args.name

        if args.config_dir is None:
            args.config_dir = args.dest

        script = ScriptComposer()

        script.command(f"umask {args.umask}")
        script.newline()

        script.command(f"export PAV_CONFIG_DIR=\"{args.config_dir.resolve()}\"")
        script.command(f"PAVBIN=\"{pav_bin}\"")
        script.newline()

        script.comment("Only prepend PAVBIN to path if it hasn't already been done.")
        script.command("if [[ ! (\"${PATH}\" =~ \"${PAVBIN}\") ]]; then")
        script.command("    export PATH=\"${PAVBIN}:${PATH}\"")
        script.command("fi")
        script.newline()

        script.comment("Source the script for the cd command.")
        script.command(f"source {this_dir / 'cd.sh'}")
        script.newline()

        script.command("echo \"PAVBIN         -- ${PAVBIN}\"")
        script.command("echo \"PAV_CONFIG_DIR -- ${PAV_CONFIG_DIR}\"")

        script.write(script_path)

        script_path.chmod(774)
