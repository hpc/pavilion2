"""Functions to dynamically generate test files."""

from pathlib import Path
from typing import List, Union, TextIO, Any

from pavilion import resolve
from pavilion import utils
from pavilion import variables
from pavilion.variables import VariableSetManager
from pavilion.config_dir import ConfigDirectory
from pavilion.errors import TestConfigError
from pavilion.micro import first


def create_file(dest: Union[str, Path], rel_path: Path, contents: List[str],
                newlines='\n'):
    """Create a file from the given content lines."""

    dest = verify_path(dest, rel_path)

    # Create file parent directory(ies).
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Don't try to overwrite a symlink without removing it first.
    if dest.is_symlink():
        dest.unlink()

    try:
        # Write file.
        with dest.open('w') as file_:
            write_file(contents, file_, newlines=newlines)

    except OSError as err:
        raise TestConfigError("Error writing create_file/template at '{}'"
                              .format(dest), err)


def write_file(contents: List[str], outfile: TextIO, newlines='\n'):
    """Write the file contents to the given outfile. This is kept seperate so we can
    create and hash simulated files in the builder."""

    for line in contents:
        outfile.write("{}{}".format(line, newlines))


def verify_path(dest, rel_path) -> Path:
    """Verify that the given dest is reasonable relative to rel_path. Returns the full path."""
    if Path(dest).is_absolute():
        raise TestConfigError("Only relative paths are allowed as the 'create_file' or "
                              "'templates' destination. Got".format(dest))

    file_path = rel_path / dest
    # Prevent files from being written outside build directory.
    if not utils.dir_contains(file_path, rel_path, symlink_ok=True):
        raise TestConfigError("'create_file/templates: {}': file path"
                              " outside build context.".format(file_path))
    # Prevent files from overwriting existing directories.
    if file_path.is_dir():
        raise TestConfigError("'create_files/templates: {}' clashes with"
                              " existing directory in build dir.".format(file_path))

    return file_path


def resolve_template(cfg_dir: ConfigDirectory, template_fname: str,
                     var_man: VariableSetManager) -> Any:
    """Resolve a single template file specified in the test config. Return a resolved
    component."""

    tmpl_paths = list(cfg_dir.find_file(template_fname, ['suites', 'test_src']))

    if len(tmpl_paths) == 0:
        raise TestConfigError(f"Template file '{template_fname}' from 'templates' does not exist "
                              "in the 'suites' or 'test_src' subdirectories of the pavilion "
                              f"configuration directory ({cfg_dir}). (Note that it must be either "
                              "in the Pavilion config area's 'suites' or 'test_src' directory - "
                              "NOT the build directory.)")
    elif len(tmpl_paths) > 1:
        raise TestConfigError(f"Multiple matches found for '{template_fname}' in the following "
                              f"locations: {tmpl_paths}. Please remove or rename the templates to "
                              "disambiguate them.")

    tmpl_path = first(tmpl_paths)

    try:
        with tmpl_path.open() as tmpl_file:
            tmpl_lines = tmpl_file.readlines()
    except OSError as err:
        raise TestConfigError("Error reading template file '{}'".format(tmpl_path), err)

    try:
        return resolve.section_values(tmpl_lines, var_man)
    except TestConfigError as err:
        raise TestConfigError("Error resolving template '{}'"
                              .format(tmpl_path), err)
