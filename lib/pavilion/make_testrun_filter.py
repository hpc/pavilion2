"""This module contains functions to generate a generic filter function that
can passed arguments to dir_db to help filter results from TestRuns."""

from pavilion import dir_db
from pavilion.output import dbg_print

def build_filter(pav_cfg, json=False, tests=False, all=False, limit=10,
                 show_skipped=False, user=False, older=False, newer=False,
                 passed=False, failed=False, complete=False, incomplete=False,
                 sys_name=False, older_than=False, newer_than=False,
                 series_info=False):

    if all:
        main_path = pav_cfg.working_dir / 'series' / series_number.strip('s').zfill(7)
    else:
        main_path = pav_cfg.working_dir / 'test_runs'



    list = dir_db.select(main_path, filter_all, order_list)



    final = []
    for path in list:
        final.append(path.name.lstrip('0'))
    return final