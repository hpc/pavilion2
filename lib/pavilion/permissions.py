import grp
import logging
import os
import time
from pathlib import Path
from typing import Union


class PermissionsManager:
    """Manage permissions of files within this context. For all files
    created under the given path, securely set their permissions as the
    context exits. The group will be set to the given group, and permissions
    will mirror the owners permissions with the given umask applied.

    Final file permissions will be the owner permissions applied to both
    group and other, and then masked.
    """

    def __init__(self, path: Union[Path, str, None],
                 group: Union[str, None], umask: Union[int, str],
                 silent: bool = True):
        """Set the managed path and permission info.
        :param path: The file/directory to manage the permissions of. This is
            recursive.
        :param group: The group to set. It must exist.
        :param umask: The umask to apply. If given as a string, should be octal.
        :param silent: Whether to quietly log system errors.
        """

        if group is not None:
            self.gid = grp.getgrnam(group).gr_gid
        else:
            self.gid = None
        if isinstance(umask, str):
            umask = int(umask, 8)
        self.umask = umask
        if path is not None:
            self.path = Path(path)
        self.silent = silent
        self._orig_umask = None

        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        """We don't need to do anything here."""

        # Note that we trust that we have a reasonably secure umask already.
        # On exit, this will apply permissions according to the given umask,
        # rather than the system one.

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Recursively set the group of all files to the given group, and
        set the permissions to mirror the owners with the umask applied.
        """

        # If neither were set we don't have to do anything (we're using the
        # defaults).
        if self.umask is None and self.gid is None:
            return

        try:
            self.set_perms(self.path)

            for dir_path, dirnames, filenames in os.walk(self.path.as_posix()):
                dir_path = Path(dir_path)
                for dirname in dirnames:
                    path = dir_path/dirname
                    self.set_perms(path)

                for filename in filenames:
                    path = dir_path/filename
                    self.set_perms(path)

        except OSError as err:
            self.logger.warning(
                "Could not set permissions for path '%s': %s",
                self.path.as_posix(), str(err), exc_info=err)
            if not self.silent:
                raise

    def set_perms(self, path: Path) -> None:
        """Set the permissions for path.
        :raises OSError: When permissions can't be set.
        """

        if self.gid is not None:
            # Try to set the group to the one specified. Catch any OS errors,
            # and try again a few times.
            for i in range(5):
                try:
                    os.chown(path.as_posix(), -1, self.gid)
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                # Try one last time, but let the error propagate.
                os.chown(path.as_posix(), -1, self.gid)

        if self.umask is not None:
            # Invert the umask bits
            imask = ~self.umask

            # Get just the user permissions
            uperms = path.stat().st_mode & 0o700

            # Duplicate the user permissions into the group and other
            # permissions, then zero any bits that were set in the umask.
            perms = (uperms + (uperms >> 3) + (uperms >> 6)) & imask

            path.chmod(perms)
