
from datetime import datetime
from pathlib import Path

from pavilion import builder
from pavilion import dir_db
from pavilion import output
from pavilion import test_run
from pavilion.status_file import STATES


def delete_tests_by_date(pav_cfg, id_dir: Path, cutoff_date: datetime, verbose:
                         bool=False) -> int:

    def filter_test_by_date(path: Path) -> bool:

        try:
            test_time = datetime.fromtimestamp(path.lstat().st_mtime)
        except FileNotFoundError:
            return False

        if test_time > cutoff_date:
            return False

        complete_path = path/'RUN_COMPLETE'
        if complete_path.exists():
            return True

        try:
            test_obj = test_run.TestRun.load(pav_cfg, int(path.name))
            state = test_obj.status.current().state
            if state in (STATES.RUNNING, STATES.SCHEDULED):
                return False

        except PermissionError as err:
            err = str(err).split("'")
            output.fprint("Permission Error: {} cannot be removed."
                          .format(err[1]), color=output.RED)
            return False

        except (test_run.TestRunError, test_run.TestRunNotFoundError):
            pass

        return True

    return dir_db.delete(id_dir, filter_test_by_date, verbose)

def delete_series(id_dir: Path, verbose: bool=False) -> int:

    def filter_series(_: Path) -> bool:
        """Filter  a series based on if they have a any symlinked tests that
        still exist.
        :param _: This is a passed path object.
        :return True: If series dir can be removed.
        :return False: If series dir cannot be removed.
        """
        path = _
        for test_path in path.iterdir():
            if (test_path.is_symlink() and
                test_path.exists() and
                test_path.resolve().exists()):
                return False
        return True

    return dir_db.delete(id_dir, filter_series, verbose)
