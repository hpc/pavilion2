"""Functions to dynamically generate test files."""

from pathlib import Path
from typing import List, Union, TextIO

import pavilion.config
from pavilion import resolve
from pavilion import utils
from pavilion import variables
from pavilion.errors import TestConfigError


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


def resolve_template(pav_cfg: pavilion.config.PavConfig, template: str,
                     var_man: variables.VariableSetManager) -> List[str]:
    """Resolve each of the template files specified in the test config."""

    tmpl_path = pav_cfg.find_file(Path(template), 'test_src')
    if tmpl_path is None:
        raise TestConfigError("Template file '{}' from 'templates' does not exist in "
                              "any 'test_src' dir (Note that it must be in a Pavilion config "
                              "area's test_src directory - NOT the build directory.)"
                              .format(template))

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
