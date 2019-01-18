# This file contains assorted utility functions.

import os


def flatwalk(path, *args, **kwargs):
    """Perform an os.walk on path, but return a flattened list of every file and directory found.
    :param str path: The path to walk with os.walk.
    :param args: Any additional positional args for os.walk.
    :param kwargs: Any additional kwargs for os.walk.
    :returns: A list of all directories and files in or under the given path.
    :rtype list:
    """

    paths = []

    for dir, dirnames, filenames in os.walk(path, *args, **kwargs):
        for dirname in dirnames:
            paths.append(os.path.join(dir, dirname))

        for filename in filenames:
            paths.append(os.path.join(dir, filename))

    return paths
