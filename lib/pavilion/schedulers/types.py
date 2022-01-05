from typing import NewType, Dict, Any, List, FrozenSet

NodeInfo = NewType('NodeInfo', Dict[str, Any])
Nodes = NewType('Nodes', Dict[str, NodeInfo])
NodeList = NewType('NodeList', List[str])
NodeSet = NewType('NodeSet', FrozenSet[str])
