"""Callback functions for selecting nodes from a node list."""

from typing import List
import random as rnd


def contiguous(node_list: List[str], chunk_size: int) -> List[str]:
    """Just return a sequence of nodes.  This can probably be improved."""
    return node_list[:chunk_size]


def random(node_list: List[str], chunk_size: int) -> List[str]:
    """Select nodes randomly from the node list."""

    return rnd.sample(node_list, chunk_size)


def rand_dist(node_list: List[str], chunk_size: int) -> List[str]:
    """Divide the nodes into segments across the breadth of those available, and
    randomly choose one node from each segment."""

    picked = []
    step = len(node_list)//chunk_size

    for i in range(chunk_size):
        picked.append(node_list[i*step + rnd.randint(0, step-1)])

    return picked


def distributed(node_list: List[str], chunk_size: int) -> List[str]:
    """Pick an evenly spaced selection of nodes."""

    step = len(node_list)//chunk_size

    return [node_list[i*step] for i in range(chunk_size)]
