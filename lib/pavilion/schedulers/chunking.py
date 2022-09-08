"""Classes and functions for manage node chunks."""
import random
from typing import List, Dict, Union

from pavilion.schedulers.config import BACKFILL
from pavilion.types import NodeList, NodeSet


def contiguous(node_list: List[str], chunk_size: int) -> List[str]:
    """Just return a sequence of nodes.  This can probably be improved."""
    return node_list[:chunk_size]


def random_chunks(node_list: List[str], chunk_size: int) -> List[str]:
    """Select nodes randomly from the node list."""

    return random.sample(node_list, chunk_size)


def rand_dist(node_list: List[str], chunk_size: int) -> List[str]:
    """Divide the nodes into segments across the breadth of those available, and
    randomly choose one node from each segment."""

    picked = []
    step = len(node_list)//chunk_size

    for i in range(chunk_size):
        picked.append(node_list[i*step + random.randint(0, step-1)])

    return picked


def distributed(node_list: List[str], chunk_size: int) -> List[str]:
    """Pick an evenly spaced selection of nodes."""

    step = len(node_list)//chunk_size

    return [node_list[i*step] for i in range(chunk_size)]


class Chunks:
    """A collection of chunks and its usage information."""

    NODE_SELECTION = {
        'contiguous':  contiguous,
        'random':      random_chunks,
        'rand_dist':   rand_dist,
        'distributed': distributed,
    }

    def __init__(self, nodes: NodeList, size: Union[int, float], extra: str,
                 select: str):

        self.chunks = self._create_chunks(nodes, size, extra, select)

        self._group_usage = {}

    def __len__(self):
        """Get the number of chunks."""
        return len(self.chunks)

    def _create_chunks(self, nodes: NodeList, size: Union[int, float], extra: str,
                       select: str) -> List[NodeSet]:
        """Create chunks from the given nodelist, and return the chunk lists."""

        if isinstance(size, float):
            # Consider float sizes to be a percentage.
            size = min(int(size * len(nodes)), 1)

        chunks = []
        for i in range(len(nodes)//size):

            # Apply the selection function and get our chunk nodes.
            chunk = self.NODE_SELECTION[select](nodes, size)
            # Filter out any chosen from our node list.
            nodes = [node for node in nodes if node not in chunk]
            chunks.append(chunk)

        if nodes and extra == BACKFILL:
            backfill = chunks[-1][:size - len(nodes)]
            chunks.append(backfill + nodes)

        chunk_info = []
        for chunk in chunks:
            chunk_info.append(NodeSet(frozenset(chunk)))

        return chunk_info

    def get_group_chunk(self, group: str) -> (int, NodeList):
        """Return the next chunk for the given group. Chunking groups reuse chunks
         only when all chunks have been reused by the group. The exception is groups
         that are named for a numerical chunk index - they always use that chunk (modulus
         the number of chunks). Given a choice of chunks, chunks are returned according to
         overall usage (iteratively - we can't know what chunks later tests will request).

         :returns: Returns the chunk id and the nodelist for that chunk."""

        if group.isdigit():
            chunk_id = int(group) % len(self.chunks)
            return chunk_id, self.chunks[chunk_id]

        # Initialize the group usage if it's a new group.
        if group not in self._group_usage:
            if group not in self._group_usage:
                order = list(range(len(self.chunks)))
                random.shuffle(order)
                self._group_usage[group] = order

        chunk_id = self._group_usage[group].pop(0)
        self._group_usage[group].append(chunk_id)

        return chunk_id, self.chunks[chunk_id]


class ChunkSetManager:
    """Organizes chunk lists by chunk properties and node_list id."""

    # These are the properties that differentiate different sets of chunks.
    CHUNK_SELECT_PROPS = [
        'extra',
        'node_selection',
        'size',
    ]

    def __init__(self):
        self._chunk_sets = {}

    # NOTE: nid stands for nodelist ID. It's a unique id that identifies which list of
    # nodes that each set of chunks belong to.
    def _mk_id_tuple(self, nid: int, chunking: dict):
        """Create a hashable tuple from the node_list id and properties."""

        return (nid,) + tuple(chunking[prop] for prop in self.CHUNK_SELECT_PROPS)

    def get_chunk_set(self, nid, chunking: dict) -> Chunks:
        """Get the chunk_set for the given chunking properties."""

        id_tpl = self._mk_id_tuple(nid, chunking)
        if id_tpl not in self._chunk_sets:
            # This should never happen (we should always call has_chunk_set first.
            raise KeyError("Chunk set with properties {} does not exist for node_list {}."
                           .format(chunking, nid))

        return self._chunk_sets[id_tpl]

    def has_chunk_set(self, nid, chunking: Dict):
        """Return whether a chunk set exists for the given nodelist and chunking
        properties."""
        return self._mk_id_tuple(nid, chunking) in self._chunk_sets

    def create_chunk_set(self, nid, chunking, nodes) -> Chunks:
        """"""

        id_tpl = self._mk_id_tuple(nid, chunking)

        chunk_size = chunking['size']
        # Chunk size 0/null is all the nodes.
        if chunk_size in (0, None) or chunk_size > len(nodes):
            chunk_size = len(nodes)
        extra = chunking['extra']
        select = chunking['node_selection']

        chunks = Chunks(nodes, chunk_size, extra, select)
        self._chunk_sets[id_tpl] = chunks
        return chunks

