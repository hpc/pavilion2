from pathlib import Path
from typing import List

from pavilion.micro import listfilter
from pavilion.path_utils import with_suffixes


YAML_SUFFIXES = (".yaml", ".yml", ".YAML", ".YML")
SUITE_CONFIG_STEM = "suite"


def get_yaml_files(cls, dir: Path) -> List[Path]:
    """Get a list of all yaml files in the given directory."""

    return listfilter(is_yaml_file, dir.iterdir())

def is_yaml_file(file: Path) -> bool:
    """Determine whether the given file is a yaml file."""

    return file.suffix in YAML_SUFFIXES and file.is_file()

def is_suite_dir(cls, dir: Path) -> bool:
    """Determine whether the given directory is a suite directory."""

    return any(filter(lambda x: x.stem == SUITE_CONFIG_STEM, get_yaml_files(dir)))

def yaml_fnames(stem: str) -> List[Path]:
    """Get all possible yaml filename variants with the given stem."""

    return list(with_suffixes(Path(stem), YAML_SUFFIXES))

