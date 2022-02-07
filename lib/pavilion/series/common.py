"""Common functions and globals"""

from pavilion import status_file
import datetime as dt
import json

COMPLETE_FN = 'SERIES_COMPLETE'
STATUS_FN = 'status'

# This is needed by both the series object and the series info object.
def set_complete(path, when: float = None):
    """Write a file in the series directory that indicates that the series
    has finished."""

    complete_fn = path/COMPLETE_FN
    status_fn = path/STATUS_FN

    series_status = status_file.SeriesStatusFile(status_fn)
    if not complete_fn.exists():
        if when is None:
            when = time.time()

        series_status.set(status_file.SERIES_STATES.COMPLETE, "Series has completed.")
        complete_fn_tmp = complete_fn.with_suffix('.tmp')
        with complete_fn_tmp.open('w') as series_complete:
            json.dump({'complete': when}, series_complete)

        complete_fn_tmp.rename(complete_fn)


def get_complete(series_path, check_tests=False) -> Union[dict, None]
    """Get the series completion timestamp. Returns None when not complete.
    
    :param check_tests: Check tests for completion and set completion if all
        tests are complete.
    """

        complete_fn = series_path/COMPLETE_FN
        if complete_fn.exists():
            try:
                with complete_fn.open() as complete_file:
                    return json.load(complete_file)
            except (OSError, json.decoder.JSONDecodeError):
                return None

        if set_if_complete


        if not complete_fn.exists():
            if all([(test_path / TestRun.COMPLETE_FN).exists()
                    for test_path in self._tests]):
                when = max([(test_path / TestRun.COMPLETE_FN).stat().st_mtime
                            for test_path in self._tests]
                            
                common.set_complete(self.path, when)

        if complete_fn.exists():


