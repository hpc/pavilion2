Regex Result Parser (regex)
===========================

Finds matches to the given regex in the results file. The matched
string/s is/are returned as the result.

+-----------------+--------------+----------------------+--------+
| Additional Key  | Description  | Required/Optional    | Notes  |
+=================+==============+======================+========+
| regex           | Python regex | Required             |        |
|                 | to use to    |                      |        |
|                 | search file  |                      |        |
+-----------------+--------------+----------------------+--------+
| threshold       | Looks at the | Optional, default: 0 |
|                 | number of    |                      |
|                 | instances of |                      |
|                 | the regex    |                      |
+-----------------+--------------+----------------------+--------+
| expected        | Expected     | Optional             |        |
|                 | value or     |                      |        |
|                 | range(s)     |                      |        |
+-----------------+--------------+----------------------+--------+

Example:

::

    results:
        regex:
            key: result
            regex: "<results> PASSED"
            action: "store_true"
