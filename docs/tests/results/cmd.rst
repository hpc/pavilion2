Command Result Parser (cmd)
===========================

The command result parser runs a given command and puts the result of
the command into the results. The result of the command can either be
the output or the return value.

+----------------+----------------+----------------+-------------+
| Additional Key | Description    | Required/Optio | Notes       |
|                |                | nal            |             |
+================+================+================+=============+
| command        | command that   | Required       |             |
|                | will be run    |                |             |
+----------------+----------------+----------------+-------------+
| success        | what the       | Optional,      | Can either  |
|                | result parser  | default:\ ``re | be          |
|                | looks at       | turn_value``   | ``output``  |
|                |                |                | or          |
|                |                |                | ``return_va |
|                |                |                | lue``       |
+----------------+----------------+----------------+-------------+
| stderr\_out    | where stderr   | Optional,      | Can either  |
|                | will be        | default:       | be ``null`` |
|                | redirected     | ``stdout``     | or          |
|                |                |                | ``stdout``  |
+----------------+----------------+----------------+-------------+

Example:

::

    results:
        command: 
            key: cmd
            command: "abc"
            success: "return_value"

The ``results.json`` will look something like this:
``{"cmd": "127", "result": "PASS",  "name": "cmd_rp_test"}``. The key
``cmd`` has a value of ``127`` because ``abc`` is not a real command and
therefore returned the error code 127.
