from argparse import ArgumentParser, Namespace
from pathlib import Path

from pavilion import output
from pavilion.config import PavConfig
from pavilion.scriptcomposer import ScriptComposer
from .base_classes import Command


class MakeActivateCommand(Command):
    """Make the 'activate' bash script."""

    DEFAULT_SCRIPT_NAME = "activate.sh"
    PAV_CD_PATH = Path("lib/pavilion/commands/cd.sh")

    def __init__(self):
        super().__init__(
            "make-activate",
            "Make the bash script to activate Pavilion.",
            short_help="Make Pavilion activation script"
        )

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        """Setup the argument parser for the `make-activate` command."""

        parser.add_argument("file",
                            help="File to which the script will be written. "
                                 f"Defaults to ./{self.DEFAULT_SCRIPT_NAME}.",
                            type=Path, default=self.DEFAULT_SCRIPT_NAME, nargs="?")
        parser.add_argument("-c", "--config-dir",
                            help="Config directory location. If none is provided, the script "
                                 "derives the value from the directory in which it is run.",
                            type=Path)
        parser.add_argument("-p", "--pav-src",
                            help="Name of the Pavilion source directory. If none is provided, "
                                 "defaults to using the name of the root directory of the current "
                                 "Pavilion repository.")
        parser.add_argument("-f", "--force",
                            help="Forcibly overwrite the file, if a file with that name "
                                 "already exists.")

    def run(self, pav_cfg: PavConfig, args: Namespace) -> int:
        """Run the `make-activate` command."""

        if args.pav_src is None:
            args.pav_src = Path(__file__).parents[3].name

        pav_bin_dir = f"{args.pav_src}/bin"
        pav_cd_path = f"{args.pav_src}/{str(self.PAV_CD_PATH)}"

        # Don't write a shebang, since the script will be sourced
        script = ScriptComposer(header=None)

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

        if args.file.exists() and not args.force:
            output.fprint(self.errfile, f"File {args.name} already exists. Refusing to overwrite "
                                        "it. Use pav make-activate --force to overwrite.")

            return 1

        try:
            script.write(args.file)
        except OSError as err:
            # TODO: Don't print the traceback
            output.fprint(self.errfile, f"Error writing {script_path}: {err}")

            return 1

        return 0
