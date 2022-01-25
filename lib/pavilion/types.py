from pathlib import Path
from typing import NewType, Tuple, Dict, Any, List, FrozenSet, Union

# pylint: disable=invalid-name
ID_Pair = NewType('ID_Pair', Tuple[Path, int])
NodeInfo = NewType('NodeInfo', Dict[str, Any])
Nodes = NewType('Nodes', Dict[str, NodeInfo])
NodeList = NewType('NodeList', List[str])
NodeSet = NewType('NodeSet', FrozenSet[str])
NodeRange = NewType('NodeRange', Tuple[int, int])
PickedNodes = NewType('PickedNodes', Union[NodeList, NodeRange])
