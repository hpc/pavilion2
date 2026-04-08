from argparse import ArgumentParser, Namespace
from pathlib import Path

from pavilion.config import PavConfig
from pavilion.scriptcomposer import ScriptComposer
from .base_classes import Command


class MakeActivateCommand(Command):
    """Make the 'activate' bash script."""

    DEFAULT_SCRIPT_NAME = "activate.sh"

    def __init__(self):
        super().__init__(
            "make-activate",
            "Make the bash script to activate Pavilion.",
            short_help="Make Pavilion activation script"
        )

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        """Setup the argument parser for the `make-activate` command."""

        parser.add_argument("dest",
                            help="Location in which to save the script. "
                                 "Defaults to the current directory.",
                            type=Path, default=Path("."), nargs="?")
        parser.add_argument("-n", "--name",
                            help="Name of the script. Defaults to activate.sh.",
                            default=self.DEFAULT_SCRIPT_NAME)
        parser.add_argument("-c", "--config-dir",
                            help="Config directory location. If none is provided, the script "
                                 "derives the value from the directory in which it is run.",
                            type=Path)
        parser.add_argument("-u", "--umask",
                            help="Umask value to set in the script. "
                                  "Defaults to using the umask defined in pavilion.yaml")
        parser.add_argument("-p", "--pav-src",
                            help="Name of the Pavilion source directory. If none is provided, "
                                 "defaults to using the name of the root directory of the current "
                                 "Pavilion repository.")

    def run(self, pav_cfg: PavConfig, args: Namespace) -> None:
        """Run the `make-activate` command."""

        script_path = args.dest / args.name

        if args.umask is None:
            args.umask = pav_cfg.umask

        if args.pav_src is None:
            args.pav_src = Path(__file__).parents[3].name

        pav_bin_dir = f"{args.pav_src}/bin"
        pav_cd_path = f"{args.pav_src}/lib/pavilion/commands/cd.sh"

        # Don't write a shebang, since the script will be sourced
        script = ScriptComposer(header=None)

        script.command(f"umask {args.umask}")
        script.newline()

        if args.config_dir is None:
            script.command("this_dir=$(readlink -f \"$(dirname \"${BASH_SOURCE[0]}\")\")")
            script.newline()
            script.command("export PAV_CONFIG_DIR=\"${this_dir}\"")
        else:
            script.command(f"PAV_CONFIG_DIR=\"{str(args.config_dir)}\"")
            script.command("if [[ -d $PAV_CONFIG_DIR ]]; then")
            script.command("    export PAV_CONFIG_DIR")
            script.command("else")
            script.command("    echo \"ERROR: PAV_CONFIG_DIR NOT SET: ${PAV_CONFIG_DIR} "
                           "is not a directory.\" >&2")
            script.command("    return 1")
            script.command("fi")
            script.newline()

        script.command(f"PAVBIN=\"${{PAV_CONFIG_DIR}}/{pav_bin_dir}\"")
        script.command("echo \"THISPATH: $(readlink -f $PWD)\"")
        script.command("echo \"PAVCPATH: $(readlink -f $PAV_CONFIG_DIR)\"")
        script.command("echo \"BASH_SOURCE: ${BASH_SOURCE[0]}\"")
        script.newline()

        script.comment("Only prepend PAVBIN to path if it hasn't already been done.")
        script.command("if [[ -d $PAVBIN ]]; then")
        script.command("    export PAVBIN")
        script.command("    if [[ ! (\"${PATH}\" =~ \"${PAVBIN}\") ]]; then")
        script.command("        export PATH=\"${PAVBIN}:${PATH}\"")
        script.command("    fi")
        script.command("else")
        script.command("    echo \"ERROR: PAVBIN NOT SET: ${PAVBIN} is not a directory.\" >&2")
        script.command("    echo \"       PERHAPS git submodule update "
                       "--init --recursive hasn't been run.\" >&2")
        script.command("    return 1")
        script.command("fi")
        script.newline()

        script.comment("Source the script for the cd command.")
        script.command(f"source \"${{PAV_CONFIG_DIR}}/{pav_cd_path}\"")
        script.newline()

        script.command("echo \"Success:\"")
        script.command("echo \"  PAVBIN         -- ${PAVBIN}\"")
        script.command("echo \"  PAV_CONFIG_DIR -- ${PAV_CONFIG_DIR}\"")
        script.command(f"echo \"  PAV COMMIT     -- $(cd ${{PAV_CONFIG_DIR}}/{pav_bin_dir} "
                       "&& git rev-parse HEAD)\"")

        script.write(script_path)
