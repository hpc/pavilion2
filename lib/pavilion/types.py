from pathlib import Path
from typing import NewType, Tuple

# pylint: disable=invalid-name
ID_Pair = NewType('ID_Pair', Tuple[Path, int])
